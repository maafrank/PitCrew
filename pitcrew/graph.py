"""LangGraph orchestration and supervisor node."""

import json
from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph, END

from pitcrew.config import Config
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
        """Handle /init command - create AI-generated AGENTS.md.

        Returns:
            Status message
        """
        from rich.console import Console
        console = Console()

        # Check if AGENTS.md already exists
        agents_path = self.project_root / "AGENTS.md"
        if agents_path.exists():
            return "- AGENTS.md already exists (skipped)"

        console.print("📊 Building file index...")
        # Load index
        index = self.file_index.load_from_disk()
        if not index:
            index = self.file_index.build()
            self.file_index.save_to_disk(index)

        console.print(f"📁 Found {len(index.files)} files in project")

        # Gather project information
        project_name = self.project_root.name
        languages = list(index.summary.get("languages", {}).keys())
        total_files = index.summary.get("total_files", 0)

        # Detect test command
        test_commands = self.tester.detect()
        test_command = test_commands[0] if test_commands else None

        # Build file tree
        file_tree = self._build_file_tree(index)

        # Categorize files by type
        skip_extensions = {'.pdf', '.doc', '.docx', '.log', '.dat', '.bin', '.exe', '.zip', '.tar', '.gz'}

        all_summaries = []
        files_read = 0
        files_skipped = 0

        console.print("📖 Summarizing files with AI...")
        for f in index.files:
            file_path = f["path"]
            file_size = f.get("size", 0)
            ext = Path(file_path).suffix.lower()

            # Skip binary/large files completely
            if ext in skip_extensions or file_size > 1_000_000:
                files_skipped += 1
                continue

            console.print(f"  📄 Summarizing {file_path}...")
            summary = self._summarize_file(file_path)
            if summary and not summary.startswith("Error"):
                all_summaries.append(f"=== {file_path} ===\n{summary}")
                files_read += 1
            else:
                console.print(f"    ⚠️  Failed to summarize: {summary}")
                files_skipped += 1

        console.print(f"✅ Summarized {files_read} files, skipped {files_skipped} files")
        console.print(f"📝 Generating AGENTS.md with AI...")

        files_context = "\n\n".join(all_summaries) if all_summaries else "No files found"

        # Use LLM to generate AGENTS.md
        prompt = f"""You are creating an AGENTS.md file for a project. This file will be used by AI coding assistants to understand the project structure, conventions, and how to work with the codebase.

Project Information:
- Name: {project_name}
- Languages: {', '.join(languages)}
- Total Files: {total_files}
- Test Command: {test_command or 'Not detected'}

File Structure:
```
{file_tree}
```

AI-Generated Summaries of All Files:
{files_context}

Based on the detailed file summaries above, create a comprehensive AGENTS.md file.

IMPORTANT: Use the DETAILED information from the file summaries. Include:
- Actual class names, function names, and signatures
- Specific configuration values and constants
- Real import statements and dependencies
- Actual code patterns and conventions found in the files

Create sections:

1. **Project Overview**
   - What this project does
   - Main use cases and goals

2. **Tech Stack**
   - Languages and versions
   - ALL major dependencies (from the imports)
   - Key libraries and what they're used for

3. **Architecture**
   - Directory structure and purposes
   - Key files and their roles
   - Main classes and their responsibilities
   - Data flow and component interactions

4. **Key Classes & Functions**
   - List ACTUAL class names with purposes
   - List ACTUAL function signatures from the code
   - Explain what each major component does

5. **Configuration & Setup**
   - Environment variables (with actual names)
   - Configuration files and their keys
   - Setup steps
   - How to run the project

6. **How to Test**
   - Test commands
   - Testing approach

7. **Coding Conventions**
   - Patterns observed in the code
   - Style guidelines
   - Error handling approaches
   - Common practices

8. **Important Implementation Details**
   - Key algorithms or approaches
   - Important business logic
   - Gotchas or edge cases
   - TODOs or known issues

9. **AI Agent Workflow**
   - How to work with this codebase
   - Where to make common changes
   - What to be careful about

DO NOT SUMMARIZE OR SIMPLIFY. Include the specific details from the file summaries. An AI coding assistant needs concrete information, not high-level overviews.

Generate ONLY the markdown content for AGENTS.md, no additional commentary."""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.complete(messages, temperature=0.3)
            agents_content = response["content"]

            # Write AGENTS.md
            success, error = self.read_write.write("AGENTS.md", agents_content)
            if success:
                return "✓ Created AI-generated AGENTS.md based on project analysis"
            else:
                return f"✗ Failed to create AGENTS.md: {error}"

        except Exception as e:
            return f"✗ Error generating AGENTS.md: {str(e)}"

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
        """Load context documents (AGENTS.md).

        Returns:
            List of document contents
        """
        docs = []

        for filename in ["AGENTS.md", "AGENTS.local.md"]:
            path = self.project_root / filename
            if path.exists():
                success, content, _ = self.read_write.read(filename)
                if success:
                    docs.append(content)

        return docs

    def _summarize_file(self, path: str) -> str:
        """Generate an AI summary of a file using a standalone LLM call.

        Args:
            path: File path to summarize

        Returns:
            Structured summary of the file
        """
        # Read the entire file
        success, content, error = self.read_write.read(path)
        if not success:
            return f"Error reading {path}: {error}"

        # Create a standalone LLM call with NO conversation context
        summary_prompt = f"""Analyze this file in DETAIL and provide a comprehensive technical summary.

File: {path}

Content:
```
{content}
```

Structure your response EXACTLY as follows:

## Overview
[2-3 sentences describing what this file does, its purpose, and how it fits in the project]

## Imports & Dependencies
- List ALL import statements
- Note what each major dependency is used for

## Classes

### ClassName1
**Purpose:** [What this class does]

**Attributes:**
- `attribute_name: type` - description
- `another_attr: type` - description

**Methods:**
- `__init__(self, param1: type, param2: type)` - initialization
- `method_name(self, param: type) -> return_type` - what it does
- `another_method(self, param1: type, param2: type) -> return_type` - what it does

### ClassName2
[Same structure as above for each class]

## Functions

- `function_name(param1: type, param2: type) -> return_type`
  - Purpose: what it does
  - Important details or side effects

- `another_function(param: type) -> return_type`
  - Purpose: what it does
  - Important details or side effects

## Constants & Configuration
- `CONSTANT_NAME = value` - description
- `CONFIG_KEY = value` - description
- Environment variables: `ENV_VAR_NAME`

## Important Implementation Details
- Key algorithms or patterns used
- Error handling approach
- Notable business logic
- TODOs or FIXMEs

Be EXHAUSTIVE. List EVERY class, EVERY method with full signatures, EVERY function. This documentation will be used by AI coding assistants."""

        try:
            messages = [{"role": "user", "content": summary_prompt}]
            response = self.llm.complete(messages, temperature=0.3)
            return response["content"]
        except Exception as e:
            return f"Error summarizing {path}: {str(e)}"

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
