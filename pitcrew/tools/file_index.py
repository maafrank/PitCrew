"""File indexing tool for project analysis."""

import hashlib
import json
from pathlib import Path
from typing import Optional

from pitcrew.constants import LANGUAGE_MAP
from pitcrew.utils.ignore import IgnoreRules


class FileIndexSnapshot:
    """Snapshot of project file index."""

    def __init__(self, files: list[dict], summary: dict):
        """Initialize snapshot.

        Args:
            files: List of file metadata dicts
            summary: Summary statistics
        """
        self.files = files
        self.summary = summary

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "files": self.files,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileIndexSnapshot":
        """Create from dictionary."""
        return cls(files=data["files"], summary=data["summary"])


class FileIndex:
    """Indexes files in a project directory."""

    def __init__(
        self,
        project_root: Path,
        ignore_rules: IgnoreRules,
        max_file_size_mb: int = 100,
    ):
        """Initialize file indexer.

        Args:
            project_root: Root directory to index
            ignore_rules: Ignore rules to apply
            max_file_size_mb: Maximum file size to index (in MB)
        """
        self.project_root = project_root
        self.ignore_rules = ignore_rules
        self.max_file_size = max_file_size_mb * 1024 * 1024

    def build(self) -> FileIndexSnapshot:
        """Build file index by walking the project tree.

        Returns:
            FileIndexSnapshot with all indexed files
        """
        files = []
        total_size = 0
        language_counts: dict[str, int] = {}

        for path in self.project_root.rglob("*"):
            # Skip directories
            if path.is_dir():
                continue

            # Skip ignored files
            if self.ignore_rules.should_ignore(path):
                continue

            # Skip files that are too large
            try:
                size = path.stat().st_size
                if size > self.max_file_size:
                    continue
            except OSError:
                continue  # Skip files we can't stat

            # Determine language
            language = self._detect_language(path)

            # Calculate hash for text files (skip binary)
            file_hash = None
            if self._is_likely_text(path):
                try:
                    with open(path, "rb") as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                except (IOError, OSError):
                    pass

            # Get relative path
            try:
                rel_path = path.relative_to(self.project_root)
            except ValueError:
                continue

            # Add to index
            files.append({
                "path": str(rel_path),
                "size": size,
                "mtime": path.stat().st_mtime,
                "hash": file_hash,
                "language": language,
            })

            total_size += size

            if language:
                language_counts[language] = language_counts.get(language, 0) + 1

        summary = {
            "total_files": len(files),
            "total_size": total_size,
            "languages": language_counts,
        }

        return FileIndexSnapshot(files=files, summary=summary)

    def _detect_language(self, path: Path) -> Optional[str]:
        """Detect programming language from file extension.

        Args:
            path: File path

        Returns:
            Language name or None
        """
        suffix = path.suffix.lower()
        return LANGUAGE_MAP.get(suffix)

    def _is_likely_text(self, path: Path) -> bool:
        """Heuristic to check if file is likely text.

        Args:
            path: File path

        Returns:
            True if likely text file
        """
        # Check extension first
        if path.suffix.lower() in LANGUAGE_MAP:
            return True

        # Check for common text extensions
        text_extensions = {
            ".txt", ".md", ".rst", ".log", ".cfg", ".ini", ".conf",
            ".json", ".yaml", ".yml", ".toml", ".xml",
        }
        if path.suffix.lower() in text_extensions:
            return True

        # Try to read first few bytes
        try:
            with open(path, "rb") as f:
                chunk = f.read(512)
                # Simple heuristic: if it's mostly printable ASCII, it's probably text
                if len(chunk) == 0:
                    return True
                printable_ratio = sum(1 for b in chunk if 32 <= b < 127 or b in (9, 10, 13)) / len(chunk)
                return printable_ratio > 0.7
        except (IOError, OSError):
            return False

    def save_to_disk(self, snapshot: FileIndexSnapshot) -> None:
        """Save index snapshot to .bot/index.json.

        Args:
            snapshot: Snapshot to save
        """
        index_path = self.project_root / ".bot" / "index.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)

        with open(index_path, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

    def load_from_disk(self) -> Optional[FileIndexSnapshot]:
        """Load index snapshot from .bot/index.json.

        Returns:
            FileIndexSnapshot if exists, None otherwise
        """
        index_path = self.project_root / ".bot" / "index.json"

        if not index_path.exists():
            return None

        try:
            with open(index_path) as f:
                data = json.load(f)
                return FileIndexSnapshot.from_dict(data)
        except (json.JSONDecodeError, IOError, KeyError):
            return None

    def summarize(self, snapshot: FileIndexSnapshot) -> str:
        """Generate human-readable summary of index.

        Args:
            snapshot: Snapshot to summarize

        Returns:
            Summary string
        """
        summary = snapshot.summary
        total_files = summary["total_files"]
        total_size_mb = summary["total_size"] / (1024 * 1024)
        languages = summary["languages"]

        lines = [
            f"Indexed {total_files} files ({total_size_mb:.2f} MB)",
        ]

        if languages:
            lang_list = ", ".join(f"{lang}: {count}" for lang, count in sorted(languages.items()))
            lines.append(f"Languages: {lang_list}")

        return "\n".join(lines)
