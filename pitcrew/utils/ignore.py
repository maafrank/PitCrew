"""File ignore rules handling using pathspec."""

from pathlib import Path
from typing import Optional

import pathspec

from pitcrew.constants import BUILTIN_IGNORES


class IgnoreRules:
    """Handles file ignore rules from .gitignore and .codebotignore."""

    def __init__(self, project_root: Path):
        """Initialize ignore rules.

        Args:
            project_root: Root directory to search for ignore files
        """
        self.project_root = project_root
        self.spec = self._build_spec()

    def _build_spec(self) -> pathspec.PathSpec:
        """Build combined PathSpec from all ignore sources."""
        patterns = list(BUILTIN_IGNORES)

        # Load .gitignore
        gitignore_path = self.project_root / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path) as f:
                    patterns.extend(f.read().splitlines())
            except IOError:
                pass  # Ignore read errors

        # Load .codebotignore (takes precedence)
        codebotignore_path = self.project_root / ".codebotignore"
        if codebotignore_path.exists():
            try:
                with open(codebotignore_path) as f:
                    patterns.extend(f.read().splitlines())
            except IOError:
                pass  # Ignore read errors

        # Filter out empty lines and comments
        patterns = [p.strip() for p in patterns if p.strip() and not p.strip().startswith("#")]

        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored.

        Args:
            path: Path to check (can be absolute or relative)

        Returns:
            True if the path should be ignored
        """
        # Convert to relative path from project root
        try:
            if path.is_absolute():
                rel_path = path.relative_to(self.project_root)
            else:
                rel_path = path
        except ValueError:
            # Path is outside project root
            return True

        # Check against pathspec
        return self.spec.match_file(str(rel_path))

    def get_patterns(self) -> list[str]:
        """Get all ignore patterns.

        Returns:
            List of pattern strings
        """
        return self.spec.patterns
