"""LangGraph orchestration and supervisor node."""

import json
import time
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

        # Initialize LLM (Anthropic only)
        model_descriptor = LLM.parse_model_string(config.default_model)
        if not config.anthropic_api_key:
            raise ValueError("No Anthropic API key found. Set ANTHROPIC_API_KEY in .env")
        self.llm = LLM(model_descriptor, config.anthropic_api_key)

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
        """Handle /init command - create or update AI-generated AGENTS.md.

        Returns:
            Status message
        """
        from rich.console import Console
        console = Console()

        # Check if AGENTS.md already exists
        agents_path = self.project_root / "AGENTS.md"
        existing_agents_content = None
        is_update = False

        if agents_path.exists():
            is_update = True
            console.print("📄 Found existing AGENTS.md, will update it with latest changes...")
            success, content, _ = self.read_write.read("AGENTS.md")
            if success:
                existing_agents_content = content

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

        # Categorize files by type (only skip truly binary/non-code files)
        skip_extensions = {
            '.pdf', '.doc', '.docx', '.log', '.dat', '.bin', '.exe', '.zip', '.tar', '.gz',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico', '.webp',  # Images
            '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv',  # Videos
            '.mp3', '.wav', '.ogg', '.flac',  # Audio
            '.ttf', '.otf', '.woff', '.woff2',  # Fonts
        }

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

            # Show file size for context
            size_kb = file_size / 1024
            size_str = f"{size_kb:.1f}KB" if size_kb < 1024 else f"{size_kb/1024:.1f}MB"
            console.print(f"  📄 Summarizing {file_path} ({size_str})...")

            summary = self._summarize_file(file_path)
            if summary and not summary.startswith("Error"):
                all_summaries.append(f"=== {file_path} ===\n{summary}")
                files_read += 1

                # Add delay to avoid rate limits (2 seconds between summaries)
                time.sleep(2)
            else:
                console.print(f"    ⚠️  Failed to summarize: {summary}")
                files_skipped += 1

        console.print(f"✅ Summarized {files_read} files, skipped {files_skipped} files")
        console.print(f"📝 Generating AGENTS.md with AI...")

        files_context = "\n\n".join(all_summaries) if all_summaries else "No files found"

        # Build appropriate prompt based on whether this is creation or update
        if is_update and existing_agents_content:
            action_verb = "updating"
            existing_context = f"""
Existing AGENTS.md Content:
```markdown
{existing_agents_content[:5000]}
```

Your task: Review the existing AGENTS.md and UPDATE it with the latest file summaries below.
- Preserve any manually added sections or important notes
- Update outdated information with current details from the file summaries
- Add new classes, functions, or files that weren't documented before
- Remove references to deleted files or components
- Keep the same overall structure and tone
"""
        else:
            action_verb = "creating"
            existing_context = ""

        # Use LLM to generate or update AGENTS.md with chain-of-thought
        prompt = f"""You are {action_verb} an AGENTS.md file for a project. This file will be used by AI coding assistants to understand the project structure, conventions, and how to work with the codebase.
{existing_context}

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

IMPORTANT: First, analyze the project in a <thinking> section:
1. What is the primary purpose and domain of this project?
2. What are the main components and how do they interact?
3. What are the key technologies and frameworks being used?
4. What patterns and conventions are consistently used?
5. What would an AI agent need to know to effectively work on this codebase?
6. What are the most important classes, functions, and files?

Then create the AGENTS.md content in a <content> section.

Format:
<thinking>
[Your analysis of the project based on the file summaries]
</thinking>

<content>
# AGENTS.md

[The actual AGENTS.md markdown content following the structure below]
</content>

Structure for the AGENTS.md file:

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

IMPORTANT: Use DETAILED information from the file summaries. Include actual class names, function signatures, configuration values, and code patterns. An AI coding assistant needs concrete information, not high-level overviews."""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.complete(messages, temperature=0.3)
            full_response = response["content"]

            # Extract content section (ignore thinking)
            import re
            content_match = re.search(r'<content>(.*?)</content>', full_response, re.DOTALL | re.IGNORECASE)
            if content_match:
                agents_content = content_match.group(1).strip()
            else:
                # Fallback: use full response if no tags found
                agents_content = full_response

            # Write AGENTS.md
            success, error = self.read_write.write("AGENTS.md", agents_content)
            if success:
                if is_update:
                    return "✓ Updated AGENTS.md with latest project changes"
                else:
                    return "✓ Created AI-generated AGENTS.md based on project analysis"
            else:
                return f"✗ Failed to write AGENTS.md: {error}"

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

    def handle_plan(self, goal: str, conversation_history: list[dict] = None) -> tuple[Any, str]:
        """Handle /plan command - generate an edit plan.

        Args:
            goal: User's goal
            conversation_history: Recent conversation messages for context

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

        # Generate plan with conversation context
        plan = self.planner.make_plan(goal, index, context_docs, conversation_history or [])

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
                # Check if this is actually a file creation patch (@@ -0,0 +...)
                patch_content = edit.patch_unified or ""
                if "@@ -0,0 +" in patch_content:
                    # Extract content from patch
                    lines = []
                    for line in patch_content.split('\n'):
                        if line.startswith('+') and not line.startswith('+++'):
                            lines.append(line[1:])  # Remove the '+' prefix
                    content = '\n'.join(lines)
                    success, error = self.read_write.write(edit.path, content)
                    if success:
                        messages.append(f"✓ Created {edit.path} (from patch)")
                    else:
                        messages.append(f"✗ Failed to create {edit.path}: {error}")
                else:
                    # Normal patch
                    result = self.read_write.patch(edit.path, patch_content)
                    if result.success:
                        messages.append(f"✓ Patched {edit.path}")
                    else:
                        messages.append(f"✗ Failed to patch {edit.path}: {result.error}")

            elif edit.action == "implement":
                # Use the implement handler to generate code
                description = edit.description or edit.justification
                result = self.handle_implement(edit.path, description)
                messages.append(result)

            elif edit.action == "delete":
                file_path = self.project_root / edit.path
                try:
                    file_path.unlink()
                    messages.append(f"✓ Deleted {edit.path}")
                except Exception as e:
                    messages.append(f"✗ Failed to delete {edit.path}: {e}")

        # Run post-checks with auto-fix loop
        if plan.post_checks:
            messages.append("\nRunning post-checks:")
            for check in plan.post_checks:
                # Fix common command issues (python -> python3 on macOS)
                command = check.command
                if command.startswith("python ") or command == "python":
                    command = command.replace("python", "python3", 1)

                # Try up to 3 times to fix test failures
                max_retries = 3
                for attempt in range(max_retries):
                    result = self.executor.run(command, sandbox=True)

                    if result.success:
                        messages.append(f"✓ {command}")
                        break
                    else:
                        messages.append(f"✗ {command} (exit code: {result.exit_code}) [Attempt {attempt + 1}/{max_retries}]")

                        # Show error output
                        error_preview = result.stderr[:300] if result.stderr else result.stdout[:300] if result.stdout else "No output"
                        messages.append(f"  Error: {error_preview}")

                        # If this was the last attempt, give up
                        if attempt == max_retries - 1:
                            full_error = result.stderr or result.stdout or "No output"
                            messages.append(f"\n  Full error output:\n{full_error[:1000]}")
                            messages.append(f"  ⚠️  Gave up after {max_retries} attempts")
                            break

                        # Attempt to auto-fix the errors
                        messages.append(f"  🔧 Analyzing errors and attempting fix...")
                        fix_result = self._auto_fix_test_failures(command, result, plan)
                        messages.append(f"  {fix_result}")

        return "\n".join(messages)

    def _auto_fix_test_failures(self, command: str, result: Any, original_plan: Any) -> str:
        """Analyze test failures and automatically generate a fix plan.

        Args:
            command: The test command that failed
            result: Execution result with stderr/stdout
            original_plan: The original plan that was applied

        Returns:
            Status message
        """
        # Combine stdout and stderr
        error_output = f"{result.stdout}\n{result.stderr}" if result.stdout or result.stderr else "No output"

        # Build prompt for fix generation with chain-of-thought
        prompt = f"""A test command failed. Analyze the errors and determine how to fix them.

Test Command: {command}
Exit Code: {result.exit_code}

Error Output:
{error_output[:2000]}

Original Plan Intent: {original_plan.intent}

Files that were created/modified:
{chr(10).join([f"- {edit.path}" for edit in original_plan.edits])}

IMPORTANT: Think through the problem step-by-step in a <thinking> section:
1. What type of error is this? (ImportError, SyntaxError, AttributeError, logic error, etc.)
2. What is the root cause? Look at the error traceback and messages carefully.
3. Which specific files or lines are mentioned in the error?
4. Is this a missing dependency, wrong import path, missing file, or code logic issue?
5. What specific changes are needed to fix this?
6. Are there any related issues that might cause the same error again?

Then provide your analysis in an <analysis> section.

Format:
<thinking>
[Step-by-step reasoning about the error and how to fix it]
</thinking>

<analysis>
[Brief summary of what needs to be fixed and why]
</analysis>"""

        try:
            # Load context
            context_docs = self._load_context_docs()

            # Create a fix plan using the planner
            # We'll use a simplified approach: ask LLM directly for fixes
            messages = [
                {"role": "system", "content": "You are debugging test failures. Provide specific, targeted fixes."},
                {"role": "user", "content": prompt}
            ]

            response = self.llm.complete(messages, temperature=0.3)
            full_response = response["content"]

            # Extract thinking and analysis sections
            import re
            thinking_match = re.search(r'<thinking>(.*?)</thinking>', full_response, re.DOTALL | re.IGNORECASE)
            thinking = thinking_match.group(1).strip() if thinking_match else None

            analysis_match = re.search(r'<analysis>(.*?)</analysis>', full_response, re.DOTALL | re.IGNORECASE)
            analysis = analysis_match.group(1).strip() if analysis_match else full_response

            # Display thinking to console
            from rich.console import Console
            console = Console()

            if thinking:
                console.print(f"[dim]💭 Error Analysis:[/dim]")
                # Show more thinking - up to 500 chars with line breaks
                thinking_lines = thinking.split('\n')
                shown_chars = 0
                shown_lines = []
                for line in thinking_lines:
                    if shown_chars + len(line) > 500:
                        shown_lines.append("...")
                        break
                    shown_lines.append(line)
                    shown_chars += len(line)
                console.print(f"[dim]{chr(10).join(shown_lines)}[/dim]")

            # Extract file names from error messages
            import re
            file_matches = re.findall(r'File "([^"]+)"', error_output)
            files_to_fix = list(set(file_matches))  # Unique files

            # If no files found in error, try to infer from the files we just created
            if not files_to_fix:
                # Look for module/import errors that mention our files
                for edit in original_plan.edits:
                    file_name = edit.path.split('/')[-1].replace('.py', '')
                    if file_name in error_output or edit.path in error_output:
                        files_to_fix.append(edit.path)

            # If still no files, just re-implement all files from the plan
            if not files_to_fix:
                files_to_fix = [edit.path for edit in original_plan.edits if edit.action in ["implement", "create"]][:3]

            if not files_to_fix:
                return f"Analysis: {analysis[:500]} | No files identified to fix"

            # Create fix plan
            from pitcrew.tools.planner import Plan, EditAction

            fix_edits = []
            for file_path in files_to_fix[:3]:  # Limit to 3 files
                fix_edits.append(EditAction(
                    path=file_path,
                    action="implement",
                    justification=f"Fix errors in {file_path}",
                    description=f"Fix the errors found during testing. Error output shows: {error_output[:300]}. LLM analysis: {analysis[:200]}"
                ))

            if not fix_edits:
                return f"Analysis: {analysis[:300]}"

            fix_plan = Plan(
                intent="Fix test failures",
                edits=fix_edits,
                post_checks=[]
            )

            # Apply the fix plan (without post-checks to avoid infinite loop)
            result_messages = []
            for edit in fix_plan.edits:
                if edit.action == "implement":
                    description = edit.description or edit.justification
                    impl_result = self.handle_implement(edit.path, description)
                    result_messages.append(impl_result)

            return " | ".join(result_messages) if result_messages else "No fixes applied"

        except Exception as e:
            return f"Error during auto-fix: {str(e)}"

    def handle_implement(self, file_path: str, description: str) -> str:
        """Handle /implement command - generate code for a specific file.

        Args:
            file_path: Path to the file to implement
            description: What the file should do

        Returns:
            Status message
        """
        from rich.console import Console
        console = Console()

        console.print(f"🔨 Implementing {file_path}...")

        # Read the current file content (if it exists)
        existing_content = ""
        success, content, _ = self.read_write.read(file_path)
        if success:
            existing_content = content
            lines = len(content.split('\n'))
            console.print(f"[dim]   📖 Read existing file ({lines} lines)[/dim]")

        # Load AGENTS.md for context
        context_docs = self._load_context_docs()
        context = "\n\n".join(context_docs) if context_docs else ""

        # Build prompt for code generation with chain-of-thought
        prompt = f"""Generate complete, working code for this file.

File: {file_path}
Purpose: {description}

Project Context:
{context[:1000]}

Current Content (if exists):
{existing_content[:500] if existing_content else "File does not exist yet"}

IMPORTANT: First, think through your implementation step-by-step in a <thinking> section:
1. What is the main purpose and responsibility of this file?
2. What classes/functions/components are needed?
3. What imports and dependencies are required?
4. How does this integrate with the rest of the project (based on context)?
5. What edge cases or error handling should be included?
6. What are the specific requirements from the description?

Then provide the complete code in a <code> section.

Format your response as:
<thinking>
[Your detailed step-by-step reasoning here]
</thinking>

<code>
[The actual code content - complete and working, not TODO comments]
</code>

The code section should contain ONLY raw code with no markdown fences or explanations."""

        try:
            console.print(f"[dim]   🤖 Asking AI to generate code...[/dim]")
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.complete(messages, temperature=0.3)
            full_response = response["content"]
            console.print(f"[dim]   ✓ Received response from AI[/dim]")

            # Extract thinking and code sections
            import re

            # Try to extract thinking section
            thinking_match = re.search(r'<thinking>(.*?)</thinking>', full_response, re.DOTALL | re.IGNORECASE)
            thinking = thinking_match.group(1).strip() if thinking_match else None

            # Try to extract code section
            code_match = re.search(r'<code>(.*?)</code>', full_response, re.DOTALL | re.IGNORECASE)
            if code_match:
                generated_code = code_match.group(1).strip()
            else:
                # Fallback: try markdown code blocks
                if "```" in full_response:
                    match = re.search(r'```(?:\w+)?\n(.*?)\n```', full_response, re.DOTALL)
                    if match:
                        generated_code = match.group(1)
                    else:
                        generated_code = full_response
                else:
                    generated_code = full_response

            # Display thinking to user if present
            if thinking:
                console.print(f"[dim]💭 AI Reasoning:[/dim]")
                # Show more thinking - up to 500 chars with line breaks
                thinking_lines = thinking.split('\n')
                shown_chars = 0
                shown_lines = []
                for line in thinking_lines:
                    if shown_chars + len(line) > 500:
                        shown_lines.append("...")
                        break
                    shown_lines.append(line)
                    shown_chars += len(line)
                console.print(f"[dim]{chr(10).join(shown_lines)}[/dim]")

            # Write the file
            console.print(f"[dim]   💾 Writing code to {file_path}...[/dim]")
            success, error = self.read_write.write(file_path, generated_code)
            if success:
                lines_written = len(generated_code.split('\n'))
                return f"✓ Implemented {file_path} ({lines_written} lines)"
            else:
                return f"✗ Failed to write {file_path}: {error}"

        except Exception as e:
            return f"✗ Error generating code for {file_path}: {str(e)}"

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

        # Determine max chars based on file type
        # Code files: more generous limit
        # Data/markup files: stricter limit to avoid huge generated files
        ext = Path(path).suffix.lower()
        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.c', '.cpp', '.rb', '.php'}

        if ext in code_extensions:
            max_chars = 50_000  # ~12K tokens for code files
        else:
            max_chars = 20_000  # ~5K tokens for markup/data files (HTML, MD, JSON, etc)

        truncated = False
        original_length = len(content)
        if len(content) > max_chars:
            # For code files, try to get complete functions/classes
            # For others, just take the beginning
            content = content[:max_chars]
            truncated = True

        # Create a standalone LLM call with NO conversation context
        truncation_note = ""
        if truncated:
            truncation_note = f"\n\n[NOTE: File was truncated from {original_length:,} to {max_chars:,} characters. Only analyzing the first portion.]"

        summary_prompt = f"""Analyze this file in DETAIL and provide a comprehensive technical summary.{truncation_note}

File: {path}

Content:
```
{content}
```

IMPORTANT: First, think about the file structure in a <thinking> section:
1. What is the primary purpose of this file?
2. What are the main components (classes, functions)?
3. What external dependencies does it use?
4. What patterns or approaches are used?
5. How does it fit into the larger project?

Then provide the detailed summary in a <summary> section.

Format:
<thinking>
[Brief analysis of the file]
</thinking>

<summary>
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
</summary>

Be EXHAUSTIVE. List EVERY class, EVERY method with full signatures, EVERY function. This documentation will be used by AI coding assistants."""

        max_retries = 3
        retry_delay = 10  # seconds (increased from 5)

        for attempt in range(max_retries):
            try:
                messages = [{"role": "user", "content": summary_prompt}]
                response = self.llm.complete(messages, temperature=0.3)
                full_response = response["content"]

                # Extract summary section (ignore thinking)
                import re
                summary_match = re.search(r'<summary>(.*?)</summary>', full_response, re.DOTALL | re.IGNORECASE)
                if summary_match:
                    return summary_match.group(1).strip()
                else:
                    # Fallback: return full response if no tags found
                    return full_response
            except Exception as e:
                error_msg = str(e)
                # Check if it's a rate limit error
                if "rate_limit_error" in error_msg or "429" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)  # Exponential backoff: 10s, 20s, 30s
                        print(f"    ⚠️  Rate limit hit, waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                return f"Error summarizing {path}: {error_msg}"

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
