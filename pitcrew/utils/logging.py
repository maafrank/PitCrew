"""Session logging utilities."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class SessionLogger:
    """Handles logging for a PitCrew session."""

    def __init__(self, project_root: Path, run_id: Optional[str] = None):
        """Initialize session logger.

        Args:
            project_root: Project root directory
            run_id: Optional run ID (generated if not provided)
        """
        self.project_root = project_root
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create logs directory
        self.log_dir = project_root / ".pitcrew" / "runs" / self.run_id
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log files
        self.transcript_path = self.log_dir / "transcript.ndjson"
        self.plan_path = self.log_dir / "plan.json"
        self.diffs_dir = self.log_dir / "diffs"
        self.exec_dir = self.log_dir / "exec"

        self.diffs_dir.mkdir(exist_ok=True)
        self.exec_dir.mkdir(exist_ok=True)

    def log_message(
        self, role: str, content: str, tool_calls: Optional[list] = None
    ) -> None:
        """Log a conversation message.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
            tool_calls: Optional tool calls
        """
        entry = {
            "ts": datetime.now().isoformat(),
            "role": role,
            "content": content,
        }

        if tool_calls:
            entry["tool_calls"] = tool_calls

        with open(self.transcript_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def save_plan(self, plan: dict) -> None:
        """Save a plan to disk.

        Args:
            plan: Plan dictionary
        """
        with open(self.plan_path, "w") as f:
            json.dump(plan, f, indent=2)

    def save_diff(self, filename: str, diff_content: str) -> None:
        """Save a diff to disk.

        Args:
            filename: Name for the diff file
            diff_content: Diff content
        """
        diff_path = self.diffs_dir / f"{filename}.diff"
        with open(diff_path, "w") as f:
            f.write(diff_content)

    def save_exec_result(self, command: str, result: dict) -> None:
        """Save execution result.

        Args:
            command: Command that was executed
            result: Execution result dictionary
        """
        # Sanitize command for filename
        safe_cmd = "".join(c if c.isalnum() else "_" for c in command[:50])
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{timestamp}_{safe_cmd}.json"

        exec_path = self.exec_dir / filename
        with open(exec_path, "w") as f:
            json.dump(
                {
                    "command": command,
                    "timestamp": datetime.now().isoformat(),
                    **result,
                },
                f,
                indent=2,
            )

    def get_log_path(self) -> str:
        """Get the path to the log directory.

        Returns:
            Absolute path to log directory
        """
        return str(self.log_dir.absolute())
