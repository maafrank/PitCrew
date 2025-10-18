"""LangGraph orchestration and supervisor node."""

import json
from pathlib import Path
from typing import Any

from jinja2 import Template
from langgraph.graph import StateGraph, END

from pitcrew.config import Config
from pitcrew.constants import get_template_dir
from pitcrew.llm import LLM
from pitcrew.state import BotState
from pitcrew.tools.executor import Executor
from pitcrew.tools.file_index import FileIndex
from pitcrew.tools.planner import Planner
from pitcrew.tools.read_write import ReadWrite
from pitcrew.tools.tester import Tester
from pitcrew.utils.ignore import IgnoreRules
from pitcrew.utils.logging import SessionLogger


class PitCrewGraph:
    """Manages the LangGraph workflow for PitCrew."""

    def __init__(self, project_root: Path, config: Config):
        """Initialize the graph.

        Args:
            project_root: Project root directory
            config: Configuration object
        """
        self.project_root = project_root
        self.config = config

        # Initialize tools
        self.ignore_rules = IgnoreRules(project_root)
        self.file_index = FileIndex(project_root, self.ignore_rules, config.max_read_mb)
        self.read_write = ReadWrite(project_root, config.max_read_mb, config.max_write_mb)
        self.executor = Executor(project_root, config.exec_timeout, config.exec_net_policy)
        self.tester = Tester(project_root, self.executor, config.custom_commands)

        # Initialize LLM
        model_descriptor = LLM.parse_model_string(config.default_model)
        api_key = (
            config.openai_api_key
            if model_descriptor.provider == "openai"
            else config.anthropic_api_key
        )
        if not api_key:
            raise ValueError(f"No API key found for provider: {model_descriptor.provider}")
        self.llm = LLM(model_descriptor, api_key)

        # Initialize planner
        self.planner = Planner(self.llm, project_root)

        # Initialize logger
        self.logger: SessionLogger = None  # Set during session start

    def build_graph(self) -> StateGraph:
        """Build the LangGraph workflow.

        Returns:
            Compiled StateGraph
        """
        workflow = StateGraph(BotState)

        # Add supervisor node
        workflow.add_node("supervisor", self.supervisor_node)

        # Set entry and end points
        workflow.set_entry_point("supervisor")
        workflow.add_edge("supervisor", END)

        return workflow.compile()

    def supervisor_node(self, state: BotState) -> BotState:
        """Supervisor node that handles commands and orchestrates tools.

        Args:
            state: Current bot state

        Returns:
            Updated bot state
        """
        # This is a placeholder - actual implementation will be in the CLI
        # where we can handle interactive commands
        return state

    def handle_init(self) -> str:
        """Handle /init command - create CLAUDE.md and AGENT.md.

        Returns:
            Status message
        """
        # Load index
        index = self.file_index.load_from_disk()
        if not index:
            index = self.file_index.build()
            self.file_index.save_to_disk(index)

        # Prepare template variables
        project_name = self.project_root.name
        languages = list(index.summary.get("languages", {}).keys())

        # Detect test command
        test_commands = self.tester.detect()
        test_command = test_commands[0] if test_commands else None

        # Build simple file tree
        file_tree = self._build_file_tree(index)

        template_vars = {
            "project_name": project_name,
            "languages": languages,
            "test_command": test_command,
            "file_tree": file_tree,
            "has_python": "python" in languages,
            "has_javascript": "javascript" in languages or "typescript" in languages,
            "has_go": "go" in languages,
        }

        # Render CLAUDE.md
        claude_template_path = get_template_dir() / "CLAUDE.md.j2"
        with open(claude_template_path) as f:
            claude_template = Template(f.read())
        claude_content = claude_template.render(**template_vars)

        # Render AGENT.md
        agent_template_path = get_template_dir() / "AGENT.md.j2"
        with open(agent_template_path) as f:
            agent_template = Template(f.read())
        agent_content = agent_template.render(**template_vars)

        # Write files
        claude_path = self.project_root / "CLAUDE.md"
        agent_path = self.project_root / "AGENT.md"

        messages = []

        if not claude_path.exists():
            success, error = self.read_write.write("CLAUDE.md", claude_content)
            if success:
                messages.append("✓ Created CLAUDE.md")
            else:
                messages.append(f"✗ Failed to create CLAUDE.md: {error}")
        else:
            messages.append("- CLAUDE.md already exists (skipped)")

        if not agent_path.exists():
            success, error = self.read_write.write("AGENT.md", agent_content)
            if success:
                messages.append("✓ Created AGENT.md")
            else:
                messages.append(f"✗ Failed to create AGENT.md: {error}")
        else:
            messages.append("- AGENT.md already exists (skipped)")

        return "\n".join(messages)

    def handle_index(self) -> str:
        """Handle /index command - rebuild file index.

        Returns:
            Index summary
        """
        index = self.file_index.build()
        self.file_index.save_to_disk(index)
        return self.file_index.summarize(index)

    def handle_read(self, path: str) -> str:
        """Handle /read command - read a file.

        Args:
            path: File path to read

        Returns:
            File content or error message
        """
        success, content, error = self.read_write.read(path)
        if success:
            return f"File: {path}\n\n{content}"
        else:
            return f"Error reading {path}: {error}"

    def handle_plan(self, goal: str) -> tuple[Any, str]:
        """Handle /plan command - generate an edit plan.

        Args:
            goal: User's goal

        Returns:
            Tuple of (plan_dict, summary_message)
        """
        # Load index
        index = self.file_index.load_from_disk()
        if not index:
            index = self.file_index.build()
            self.file_index.save_to_disk(index)

        # Load context docs
        context_docs = self._load_context_docs()

        # Generate plan
        plan = self.planner.make_plan(goal, index, context_docs)

        # Save plan
        if self.logger:
            self.logger.save_plan(plan.model_dump())

        # Generate summary
        summary = self._format_plan_summary(plan)

        return plan.model_dump(), summary

    def handle_apply(self, plan_dict: dict) -> str:
        """Handle /apply command - apply a plan.

        Args:
            plan_dict: Plan dictionary

        Returns:
            Status message
        """
        from pitcrew.tools.planner import Plan

        plan = Plan(**plan_dict)

        messages = []

        # Create snapshot first
        files_to_snapshot = [edit.path for edit in plan.edits if edit.action != "create"]
        if files_to_snapshot:
            success, snapshot_id, error = self.read_write.create_snapshot(files_to_snapshot)
            if success:
                messages.append(f"✓ Created snapshot: {snapshot_id}")
            else:
                messages.append(f"⚠ Could not create snapshot: {error}")

        # Apply edits
        for edit in plan.edits:
            if edit.action == "create":
                success, error = self.read_write.write(edit.path, edit.content or "")
                if success:
                    messages.append(f"✓ Created {edit.path}")
                else:
                    messages.append(f"✗ Failed to create {edit.path}: {error}")

            elif edit.action == "replace":
                success, error = self.read_write.write(edit.path, edit.content or "")
                if success:
                    messages.append(f"✓ Replaced {edit.path}")
                else:
                    messages.append(f"✗ Failed to replace {edit.path}: {error}")

            elif edit.action == "patch":
                result = self.read_write.patch(edit.path, edit.patch_unified or "")
                if result.success:
                    messages.append(f"✓ Patched {edit.path}")
                else:
                    messages.append(f"✗ Failed to patch {edit.path}: {result.error}")

            elif edit.action == "delete":
                file_path = self.project_root / edit.path
                try:
                    file_path.unlink()
                    messages.append(f"✓ Deleted {edit.path}")
                except Exception as e:
                    messages.append(f"✗ Failed to delete {edit.path}: {e}")

        # Run post-checks
        if plan.post_checks:
            messages.append("\nRunning post-checks:")
            for check in plan.post_checks:
                result = self.executor.run(check.command, sandbox=True)
                if result.success:
                    messages.append(f"✓ {check.command}")
                else:
                    messages.append(f"✗ {check.command} (exit code: {result.exit_code})")
                    if result.stderr:
                        messages.append(f"  {result.stderr[:200]}")

        return "\n".join(messages)

    def handle_exec(self, command: str) -> str:
        """Handle /exec command - execute a command.

        Args:
            command: Command to execute

        Returns:
            Execution result summary
        """
        result = self.executor.run(command, sandbox=True)

        if self.logger:
            self.logger.save_exec_result(command, result.__dict__)

        lines = [
            f"Command: {command}",
            f"Exit code: {result.exit_code}",
            f"Duration: {result.duration_ms}ms",
        ]

        if result.stdout:
            lines.append(f"\nStdout:\n{result.stdout}")

        if result.stderr:
            lines.append(f"\nStderr:\n{result.stderr}")

        return "\n".join(lines)

    def handle_test(self) -> str:
        """Handle /test command - run tests.

        Returns:
            Test results summary
        """
        results = self.tester.run_all()
        return self.tester.get_test_summary(results)

    def handle_undo(self) -> str:
        """Handle /undo command - restore last snapshot.

        Returns:
            Status message
        """
        snapshots = self.read_write.list_snapshots()

        if not snapshots:
            return "No snapshots available to undo"

        # Restore most recent snapshot
        snapshot_id = snapshots[0]
        success, error = self.read_write.restore_snapshot(snapshot_id)

        if success:
            return f"✓ Restored snapshot: {snapshot_id}"
        else:
            return f"✗ Failed to restore snapshot: {error}"

    def _load_context_docs(self) -> list[str]:
        """Load context documents (CLAUDE.md, AGENT.md).

        Returns:
            List of document contents
        """
        docs = []

        for filename in ["CLAUDE.md", "AGENT.md", "CLAUDE.local.md"]:
            path = self.project_root / filename
            if path.exists():
                success, content, _ = self.read_write.read(filename)
                if success:
                    docs.append(content)

        return docs

    def _build_file_tree(self, index: Any) -> str:
        """Build a simple file tree representation.

        Args:
            index: File index snapshot

        Returns:
            File tree string
        """
        # Group files by directory
        tree_lines = []
        seen_dirs = set()

        for file_info in sorted(index.files, key=lambda f: f["path"])[:30]:
            path = Path(file_info["path"])

            # Add parent directories
            for parent in path.parents:
                if parent != Path(".") and str(parent) not in seen_dirs:
                    seen_dirs.add(str(parent))
                    tree_lines.append(f"{str(parent)}/")

            # Add file
            tree_lines.append(f"  {path}")

        if len(index.files) > 30:
            tree_lines.append(f"  ... and {len(index.files) - 30} more files")

        return "\n".join(tree_lines[:50])  # Limit output

    def _format_plan_summary(self, plan: Any) -> str:
        """Format a plan for display.

        Args:
            plan: Plan object

        Returns:
            Formatted summary
        """
        lines = [
            f"Intent: {plan.intent}",
            "",
            f"Edits ({len(plan.edits)}):",
        ]

        for edit in plan.edits:
            lines.append(f"  {edit.action:8} {edit.path}")
            lines.append(f"           {edit.justification}")

        if plan.post_checks:
            lines.append("")
            lines.append(f"Post-checks ({len(plan.post_checks)}):")
            for check in plan.post_checks:
                lines.append(f"  - {check.command}")

        return "\n".join(lines)
