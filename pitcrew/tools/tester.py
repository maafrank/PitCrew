"""Test discovery and execution."""

import json
from pathlib import Path
from typing import Optional

from pitcrew.tools.executor import ExecResult, Executor


class Tester:
    """Discovers and runs tests for a project."""

    def __init__(
        self,
        project_root: Path,
        executor: Executor,
        custom_commands: Optional[dict[str, str]] = None,
    ):
        """Initialize tester.

        Args:
            project_root: Project root directory
            executor: Executor instance for running commands
            custom_commands: Optional custom commands from config
        """
        self.project_root = project_root
        self.executor = executor
        self.custom_commands = custom_commands or {}

    def detect(self) -> list[str]:
        """Detect test commands for the project.

        Returns:
            List of command strings to run
        """
        # Check for custom test command first
        if "test" in self.custom_commands:
            return [self.custom_commands["test"]]

        commands = []

        # Python: pytest
        if (self.project_root / "pytest.ini").exists() or \
           (self.project_root / "tests").exists() or \
           (self.project_root / "test").exists():
            commands.append("pytest -q")

        # Node.js: npm test
        package_json = self.project_root / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    if "scripts" in data and "test" in data["scripts"]:
                        commands.append("npm test --silent")
            except (json.JSONDecodeError, IOError):
                pass

        # Go: go test
        if (self.project_root / "go.mod").exists():
            commands.append("go test ./...")

        # Rust: cargo test
        if (self.project_root / "Cargo.toml").exists():
            commands.append("cargo test --quiet")

        # Ruby: rspec or rake test
        if (self.project_root / "spec").exists():
            commands.append("rspec")
        elif (self.project_root / "Rakefile").exists():
            commands.append("rake test")

        return commands

    def run_all(self, timeout: Optional[int] = None) -> list[ExecResult]:
        """Run all detected tests.

        Args:
            timeout: Optional timeout for each test command

        Returns:
            List of ExecResults
        """
        commands = self.detect()
        results = []

        for command in commands:
            result = self.executor.run(command, timeout=timeout, sandbox=True)
            results.append(result)

        return results

    def get_test_summary(self, results: list[ExecResult]) -> str:
        """Generate a human-readable summary of test results.

        Args:
            results: List of test execution results

        Returns:
            Summary string
        """
        if not results:
            return "No tests found"

        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed

        lines = [f"Ran {total} test command(s): {passed} passed, {failed} failed"]

        for result in results:
            status = "✓" if result.success else "✗"
            lines.append(f"{status} {result.command}")
            if not result.success and result.stderr:
                # Show first few lines of error
                error_lines = result.stderr.split("\n")[:5]
                for line in error_lines:
                    lines.append(f"  {line}")

        return "\n".join(lines)
