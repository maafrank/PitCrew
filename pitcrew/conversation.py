"""Conversation context management."""

from typing import Optional

from pitcrew.tools.executor import ExecResult
from pitcrew.tools.planner import Plan


class ConversationContext:
    """Manages conversation history and context for natural language processing."""

    def __init__(self, max_history: int = 10):
        """Initialize conversation context.

        Args:
            max_history: Maximum number of message pairs to keep
        """
        self.messages: list[dict] = []
        self.current_plan: Optional[dict] = None
        self.last_files_read: list[str] = []
        self.last_execution: Optional[ExecResult] = None
        self.max_history = max_history
        self.system_prompt: Optional[str] = None

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
        """
        self.messages.append({"role": role, "content": content})

        # Trim history if too long (keep system message if exists)
        if len(self.messages) > self.max_history * 2 + 1:
            system_msgs = [m for m in self.messages if m["role"] == "system"]
            other_msgs = [m for m in self.messages if m["role"] != "system"]

            # Keep system + recent messages
            self.messages = system_msgs + other_msgs[-(self.max_history * 2) :]

    def set_system_prompt(self, prompt: str | list) -> None:
        """Set or update the system prompt.

        Args:
            prompt: System prompt content (string or structured list with cache_control)
        """
        self.system_prompt = prompt

        # Update or add system message
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = prompt
        else:
            self.messages.insert(0, {"role": "system", "content": prompt})

    def get_context_summary(self) -> str:
        """Generate a summary of recent context.

        Returns:
            Summary string
        """
        parts = []

        if self.current_plan:
            parts.append(f"Current plan: {self.current_plan.get('intent', 'N/A')}")

        if self.last_files_read:
            parts.append(f"Recently read files: {', '.join(self.last_files_read[-3:])}")

        if self.last_execution:
            parts.append(
                f"Last command: {self.last_execution.command} "
                f"(exit code: {self.last_execution.exit_code})"
            )

        return "\n".join(parts) if parts else "No recent context"

    def to_messages(self) -> list[dict]:
        """Convert to LLM message format.

        Returns:
            List of message dictionaries
        """
        return self.messages.copy()

    def update_plan(self, plan: Optional[dict]) -> None:
        """Update the current plan.

        Args:
            plan: Plan dictionary or None
        """
        self.current_plan = plan

    def add_file_read(self, file_path: str) -> None:
        """Record a file that was read.

        Args:
            file_path: Path to the file
        """
        if file_path not in self.last_files_read:
            self.last_files_read.append(file_path)

        # Keep only last 10 files
        if len(self.last_files_read) > 10:
            self.last_files_read = self.last_files_read[-10:]

    def update_execution(self, result: ExecResult) -> None:
        """Update the last execution result.

        Args:
            result: Execution result
        """
        self.last_execution = result

    def clear(self) -> None:
        """Clear conversation history (keeps system prompt)."""
        system_msgs = [m for m in self.messages if m["role"] == "system"]
        self.messages = system_msgs
        self.current_plan = None
        self.last_files_read = []
        self.last_execution = None
