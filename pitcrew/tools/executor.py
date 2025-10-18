"""Command execution with safety checks and sandboxing."""

import resource
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pitcrew.constants import DANGEROUS_PATTERNS


@dataclass
class ExecResult:
    """Result of command execution."""

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    command: str


class Executor:
    """Executes commands with safety checks and resource limits."""

    def __init__(
        self,
        project_root: Path,
        timeout: int = 45,
        network_policy: str = "deny",
    ):
        """Initialize executor.

        Args:
            project_root: Project root directory (cwd for commands)
            timeout: Timeout in seconds
            network_policy: Network policy (deny or allow)
        """
        self.project_root = project_root
        self.timeout = timeout
        self.network_policy = network_policy

    def run(
        self,
        command: str,
        timeout: Optional[int] = None,
        sandbox: bool = True,
    ) -> ExecResult:
        """Run a command.

        Args:
            command: Command to execute
            timeout: Optional timeout override
            sandbox: Whether to apply sandboxing

        Returns:
            ExecResult with execution details
        """
        # Check if command is dangerous
        is_dangerous, reason = self.is_dangerous(command)
        if is_dangerous and sandbox:
            return ExecResult(
                success=False,
                stdout="",
                stderr=f"Command blocked: {reason}",
                exit_code=-1,
                duration_ms=0,
                command=command,
            )

        timeout_val = timeout if timeout is not None else self.timeout

        # Prepare environment
        env = self._prepare_env()

        start_time = time.time()

        try:
            # Run command
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=str(self.project_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=self._setup_sandbox if sandbox else None,
            )

            # Wait with timeout
            stdout, stderr = process.communicate(timeout=timeout_val)
            exit_code = process.returncode

            duration_ms = int((time.time() - start_time) * 1000)

            return ExecResult(
                success=exit_code == 0,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=duration_ms,
                command=command,
            )

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            duration_ms = int((time.time() - start_time) * 1000)

            return ExecResult(
                success=False,
                stdout=stdout or "",
                stderr=stderr or f"Command timed out after {timeout_val}s",
                exit_code=-1,
                duration_ms=duration_ms,
                command=command,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            return ExecResult(
                success=False,
                stdout="",
                stderr=f"Execution error: {str(e)}",
                exit_code=-1,
                duration_ms=duration_ms,
                command=command,
            )

    def is_dangerous(self, command: str) -> tuple[bool, str]:
        """Check if a command matches dangerous patterns.

        Args:
            command: Command to check

        Returns:
            Tuple of (is_dangerous, reason)
        """
        for pattern, reason in DANGEROUS_PATTERNS:
            if pattern.search(command):
                return True, reason

        return False, ""

    def _prepare_env(self) -> dict[str, str]:
        """Prepare environment variables for sandboxed execution.

        Returns:
            Dictionary of environment variables
        """
        import os

        # Start with minimal environment
        env = {}

        # Keep essential variables
        keep_vars = ["PATH", "HOME", "USER", "PYTHONPATH", "VIRTUAL_ENV"]

        for var in keep_vars:
            if var in os.environ:
                env[var] = os.environ[var]

        return env

    def _setup_sandbox(self) -> None:
        """Setup resource limits for sandboxed execution.

        Called via preexec_fn before command execution.
        """
        try:
            # Set CPU time limit (60 seconds)
            resource.setrlimit(resource.RLIMIT_CPU, (60, 60))

            # Set memory limit (1GB soft, 2GB hard)
            resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 2 * 1024 * 1024 * 1024))

            # Set max processes (prevent fork bombs)
            resource.setrlimit(resource.RLIMIT_NPROC, (100, 100))

        except (ValueError, OSError):
            # If we can't set limits, continue anyway
            # (might happen on some systems or if already limited)
            pass
