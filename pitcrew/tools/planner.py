"""Planning tool for generating multi-file edit plans."""

import json
import re
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from pitcrew.llm import LLM
from pitcrew.tools.file_index import FileIndexSnapshot


class EditAction(BaseModel):
    """Represents a single file edit action."""

    path: str = Field(description="File path relative to project root")
    action: str = Field(description="Action type: create, patch, replace, or delete")
    justification: str = Field(description="Why this edit is needed")
    patch_unified: Optional[str] = Field(None, description="Unified diff for patch action")
    content: Optional[str] = Field(None, description="Full content for create/replace action")


class ExecutionAction(BaseModel):
    """Represents a command to execute."""

    command: str = Field(description="Command to execute")
    cwd: Optional[str] = Field(None, description="Working directory (default: project root)")


class Plan(BaseModel):
    """Represents a complete edit plan."""

    intent: str = Field(description="High-level description of what this plan achieves")
    files_to_read: list[str] = Field(
        default_factory=list,
        description="Files that should be read before applying edits"
    )
    edits: list[EditAction] = Field(
        default_factory=list,
        description="File edits to perform"
    )
    post_checks: list[ExecutionAction] = Field(
        default_factory=list,
        description="Commands to run after edits (tests, linters, etc.)"
    )


class Planner:
    """Generates multi-file edit plans using rule-based and LLM approaches."""

    def __init__(self, llm: LLM, project_root: Path):
        """Initialize planner.

        Args:
            llm: LLM instance for plan generation
            project_root: Project root directory
        """
        self.llm = llm
        self.project_root = project_root

    def make_plan(
        self,
        goal: str,
        index: FileIndexSnapshot,
        context_docs: list[str],
    ) -> Plan:
        """Generate a plan to achieve a goal.

        Args:
            goal: User's goal/request
            index: File index snapshot
            context_docs: Context from CLAUDE.md, AGENT.md, etc.

        Returns:
            Plan object
        """
        # Apply rule-based pre-processing
        hints = self._analyze_goal(goal, index)

        # Generate plan using LLM
        plan = self._generate_plan_llm(goal, index, context_docs, hints)

        # Validate and post-process
        plan = self._validate_plan(plan, index)

        return plan

    def _analyze_goal(self, goal: str, index: FileIndexSnapshot) -> dict[str, Any]:
        """Apply rule-based analysis to extract hints.

        Args:
            goal: User's goal
            index: File index

        Returns:
            Dictionary of hints for LLM
        """
        hints: dict[str, Any] = {
            "keywords": [],
            "likely_files": [],
            "suggested_actions": [],
        }

        goal_lower = goal.lower()

        # Detect action keywords
        if any(kw in goal_lower for kw in ["create", "add", "new"]):
            hints["keywords"].append("create")
            hints["suggested_actions"].append("Prefer creating new files over modifying existing ones")

        if any(kw in goal_lower for kw in ["refactor", "restructure", "reorganize"]):
            hints["keywords"].append("refactor")
            hints["suggested_actions"].append("Use patches for refactoring to preserve context")

        if any(kw in goal_lower for kw in ["fix", "bug", "error"]):
            hints["keywords"].append("fix")
            hints["suggested_actions"].append("Make minimal changes to fix the issue")

        if any(kw in goal_lower for kw in ["test", "tests"]):
            hints["keywords"].append("test")
            hints["suggested_actions"].append("Include post-check to run tests")

        if any(kw in goal_lower for kw in ["class", "classes"]):
            hints["suggested_actions"].append("Organize code into classes")

        # Try to identify relevant files from goal
        # Extract potential filenames or patterns
        words = re.findall(r'\b\w+\.\w+\b', goal)
        for word in words:
            # Check if this file exists in index
            for file_info in index.files:
                if word in file_info["path"]:
                    hints["likely_files"].append(file_info["path"])

        return hints

    def _generate_plan_llm(
        self,
        goal: str,
        index: FileIndexSnapshot,
        context_docs: list[str],
        hints: dict[str, Any],
    ) -> Plan:
        """Generate plan using LLM.

        Args:
            goal: User's goal
            index: File index
            context_docs: Context documents
            hints: Hints from rule-based analysis

        Returns:
            Plan object
        """
        # Build system prompt
        system_prompt = self._build_system_prompt(context_docs, hints)

        # Build user prompt
        user_prompt = self._build_user_prompt(goal, index)

        # Define tools/schema for plan generation
        plan_schema = {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "files_to_read": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "action": {
                                "type": "string",
                                "enum": ["create", "patch", "replace", "delete"],
                            },
                            "justification": {"type": "string"},
                            "patch_unified": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "action", "justification"],
                    },
                },
                "post_checks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "cwd": {"type": "string"},
                        },
                        "required": ["command"],
                    },
                },
            },
            "required": ["intent", "edits"],
        }

        # Call LLM with function calling
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "create_plan",
                    "description": "Create a structured plan to achieve the user's goal",
                    "parameters": plan_schema,
                },
            }
        ]

        try:
            response = self.llm.complete(messages, tools=tools, temperature=0.3)

            # Extract plan from tool call
            if "tool_calls" in response and response["tool_calls"]:
                tool_call = response["tool_calls"][0]
                if isinstance(tool_call["arguments"], str):
                    plan_data = json.loads(tool_call["arguments"])
                else:
                    plan_data = tool_call["arguments"]

                return Plan(**plan_data)

            # Fallback: try to parse from content
            content = response.get("content", "")
            if "```json" in content:
                # Extract JSON from markdown code block
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    plan_data = json.loads(json_match.group(1))
                    return Plan(**plan_data)

            # If we can't extract a plan, create a minimal one
            return Plan(
                intent=goal,
                files_to_read=[],
                edits=[],
                post_checks=[],
            )

        except Exception as e:
            # Return empty plan on error
            return Plan(
                intent=f"Failed to generate plan: {str(e)}",
                files_to_read=[],
                edits=[],
                post_checks=[],
            )

    def _build_system_prompt(self, context_docs: list[str], hints: dict[str, Any]) -> str:
        """Build system prompt for plan generation.

        Args:
            context_docs: Context from CLAUDE.md, etc.
            hints: Rule-based hints

        Returns:
            System prompt string
        """
        prompt_parts = [
            "You are an expert code planning assistant. Your task is to generate structured "
            "plans for code modifications.",
            "",
            "Guidelines:",
            "- Prefer patches over full file replacements when making small changes",
            "- Organize code into classes and functions",
            "- Always include tests when adding new functionality",
            "- Keep changes minimal and focused",
            "- Validate that files exist before editing (or mark for creation)",
        ]

        if hints["suggested_actions"]:
            prompt_parts.append("")
            prompt_parts.append("Specific guidance for this task:")
            for action in hints["suggested_actions"]:
                prompt_parts.append(f"- {action}")

        if context_docs:
            prompt_parts.append("")
            prompt_parts.append("Project context:")
            for doc in context_docs:
                prompt_parts.append(doc[:2000])  # Limit length

        return "\n".join(prompt_parts)

    def _build_user_prompt(self, goal: str, index: FileIndexSnapshot) -> str:
        """Build user prompt for plan generation.

        Args:
            goal: User's goal
            index: File index

        Returns:
            User prompt string
        """
        # Build file tree summary
        file_list = []
        for file_info in index.files[:50]:  # Limit to first 50 files
            file_list.append(f"- {file_info['path']} ({file_info['language'] or 'unknown'})")

        file_tree = "\n".join(file_list)

        if len(index.files) > 50:
            file_tree += f"\n... and {len(index.files) - 50} more files"

        return f"""Goal: {goal}

Project files:
{file_tree}

Please create a structured plan to achieve this goal. Use the create_plan function."""

    def _validate_plan(self, plan: Plan, index: FileIndexSnapshot) -> Plan:
        """Validate and clean up a plan.

        Args:
            plan: Plan to validate
            index: File index

        Returns:
            Validated plan
        """
        # Build set of existing files
        existing_files = {f["path"] for f in index.files}

        # Validate each edit
        for edit in plan.edits:
            # Check that create actions reference new files
            if edit.action == "create" and edit.path in existing_files:
                # Change to patch or replace
                edit.action = "replace"

            # Check that patch/replace/delete actions reference existing files
            if edit.action in ("patch", "replace", "delete") and edit.path not in existing_files:
                # Change to create if content is provided
                if edit.content:
                    edit.action = "create"

            # Validate that required fields are present
            if edit.action in ("create", "replace") and not edit.content:
                # Can't create/replace without content
                edit.action = "patch" if edit.path in existing_files else "create"

            if edit.action == "patch" and not edit.patch_unified:
                # Can't patch without a diff
                if edit.content:
                    edit.action = "replace"

        return plan
