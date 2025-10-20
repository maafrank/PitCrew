"""File reading, writing, and snapshot management."""

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from pitcrew.utils.diffs import apply_patch, normalize_line_endings


@dataclass
class PatchResult:
    """Result of applying a patch."""

    success: bool
    error: Optional[str] = None


class ReadWrite:
    """Handles file I/O operations with safety checks."""

    def __init__(
        self,
        project_root: Path,
        max_read_mb: int = 8,
        max_write_mb: int = 2,
    ):
        """Initialize ReadWrite tool.

        Args:
            project_root: Project root directory
            max_read_mb: Maximum file size to read (MB)
            max_write_mb: Maximum file size to write (MB)
        """
        self.project_root = project_root
        self.max_read_bytes = max_read_mb * 1024 * 1024
        self.max_write_bytes = max_write_mb * 1024 * 1024

    def read(self, path: str, mode: str = "auto") -> tuple[bool, Optional[str], Optional[str]]:
        """Read a file.

        Args:
            path: Relative or absolute path to file
            mode: Read mode (auto, text, binary)

        Returns:
            Tuple of (success, content, error)
        """
        file_path = self._resolve_path(path)

        # Validate path
        if not self._is_safe_path(file_path):
            return False, None, f"Path outside project root: {path}"

        if not file_path.exists():
            return False, None, f"File not found: {path}"

        if not file_path.is_file():
            return False, None, f"Not a file: {path}"

        # Check size
        try:
            size = file_path.stat().st_size
            if size > self.max_read_bytes:
                size_mb = size / (1024 * 1024)
                max_mb = self.max_read_bytes / (1024 * 1024)
                return False, None, f"File too large: {size_mb:.2f} MB (max: {max_mb} MB)"
        except OSError as e:
            return False, None, f"Cannot stat file: {e}"

        # Read file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return True, content, None
        except UnicodeDecodeError:
            return False, None, "File is not valid UTF-8 text"
        except IOError as e:
            return False, None, f"Cannot read file: {e}"

    def write(self, path: str, content: str) -> tuple[bool, Optional[str]]:
        """Write content to a file.

        Args:
            path: Relative or absolute path to file
            content: Content to write

        Returns:
            Tuple of (success, error)
        """
        file_path = self._resolve_path(path)

        # Validate path
        if not self._is_safe_path(file_path):
            return False, f"Path outside project root: {path}"

        # Check content size
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > self.max_write_bytes:
            size_mb = content_bytes / (1024 * 1024)
            max_mb = self.max_write_bytes / (1024 * 1024)
            return False, f"Content too large: {size_mb:.2f} MB (max: {max_mb} MB)"

        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write atomically (temp file + rename)
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)
            temp_path.replace(file_path)
            return True, None
        except IOError as e:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
            return False, f"Cannot write file: {e}"

    def patch(self, path: str, unified_diff: str) -> PatchResult:
        """Apply a unified diff patch to a file.

        Args:
            path: Relative or absolute path to file
            unified_diff: Unified diff string

        Returns:
            PatchResult indicating success/failure
        """
        # Read current content
        success, content, error = self.read(path)
        if not success:
            return PatchResult(success=False, error=f"Cannot read file: {error}")

        # Normalize line endings
        content = normalize_line_endings(content)
        unified_diff = normalize_line_endings(unified_diff)

        # Apply patch
        patch_success, patched_content, patch_error = apply_patch(content, unified_diff)
        if not patch_success:
            return PatchResult(success=False, error=patch_error)

        # Write back
        write_success, write_error = self.write(path, patched_content)
        if not write_success:
            return PatchResult(success=False, error=f"Cannot write file: {write_error}")

        return PatchResult(success=True)

    def create_snapshot(self, files: list[str]) -> tuple[bool, Optional[str], Optional[str]]:
        """Create a snapshot of specified files for undo.

        Args:
            files: List of file paths to snapshot

        Returns:
            Tuple of (success, snapshot_id, error)
        """
        snapshot_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        snapshot_dir = self.project_root / ".pitcrew" / "snapshots" / snapshot_id

        try:
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            for file_path_str in files:
                file_path = self._resolve_path(file_path_str)

                # Skip if file doesn't exist
                if not file_path.exists():
                    continue

                # Validate path
                if not self._is_safe_path(file_path):
                    continue

                # Get relative path for snapshot
                try:
                    rel_path = file_path.resolve().relative_to(self.project_root.resolve())
                except ValueError:
                    continue

                # Create destination path
                dest_path = snapshot_dir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy file
                shutil.copy2(file_path, dest_path)

            return True, snapshot_id, None

        except (IOError, OSError) as e:
            return False, None, f"Cannot create snapshot: {e}"

    def restore_snapshot(self, snapshot_id: str) -> tuple[bool, Optional[str]]:
        """Restore files from a snapshot.

        Args:
            snapshot_id: Snapshot ID to restore

        Returns:
            Tuple of (success, error)
        """
        snapshot_dir = self.project_root / ".pitcrew" / "snapshots" / snapshot_id

        if not snapshot_dir.exists():
            return False, f"Snapshot not found: {snapshot_id}"

        try:
            # Walk snapshot directory and restore files
            for snapshot_file in snapshot_dir.rglob("*"):
                if snapshot_file.is_dir():
                    continue

                # Get relative path
                rel_path = snapshot_file.relative_to(snapshot_dir)

                # Get destination path
                dest_path = self.project_root / rel_path

                # Create parent directories
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy file back
                shutil.copy2(snapshot_file, dest_path)

            return True, None

        except (IOError, OSError) as e:
            return False, f"Cannot restore snapshot: {e}"

    def list_snapshots(self) -> list[str]:
        """List available snapshots.

        Returns:
            List of snapshot IDs (sorted, newest first)
        """
        snapshots_dir = self.project_root / ".pitcrew" / "snapshots"

        if not snapshots_dir.exists():
            return []

        snapshots = []
        for entry in snapshots_dir.iterdir():
            if entry.is_dir():
                snapshots.append(entry.name)

        return sorted(snapshots, reverse=True)

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path string to absolute Path.

        Args:
            path: Path string (relative or absolute)

        Returns:
            Absolute Path
        """
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.project_root / p).resolve()

    def _is_safe_path(self, path: Path) -> bool:
        """Check if a path is within project root.

        Args:
            path: Absolute path to check

        Returns:
            True if path is safe (within project root)
        """
        try:
            path.resolve().relative_to(self.project_root.resolve())
            return True
        except ValueError:
            return False
