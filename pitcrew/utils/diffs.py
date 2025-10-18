"""Utilities for creating and applying diffs/patches."""

import difflib
from typing import Optional

from unidiff import PatchSet


def create_patch(original: str, modified: str, filename: str = "file") -> str:
    """Create a unified diff patch.

    Args:
        original: Original file content
        modified: Modified file content
        filename: Filename to use in patch header

    Returns:
        Unified diff string
    """
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm="",
    )

    return "".join(diff)


def apply_patch(content: str, patch_str: str) -> tuple[bool, Optional[str], Optional[str]]:
    """Apply a unified diff patch to content.

    Args:
        content: Original content
        patch_str: Unified diff string

    Returns:
        Tuple of (success, result_content, error_message)
        - success: True if patch applied successfully
        - result_content: Patched content (None if failed)
        - error_message: Error message (None if successful)
    """
    try:
        # Parse the patch
        patchset = PatchSet(patch_str)

        if len(patchset) == 0:
            return False, None, "Empty patch"

        if len(patchset) > 1:
            return False, None, "Patch contains multiple files"

        # Get the single file patch
        patched_file = patchset[0]

        # Split content into lines
        lines = content.splitlines(keepends=True)

        # Apply hunks in reverse order to maintain line numbers
        for hunk in reversed(patched_file):
            # Get source starting line (1-indexed in diff, 0-indexed in list)
            source_start = hunk.source_start - 1
            source_length = hunk.source_length

            # Build new lines from hunk
            new_lines = []
            for line in hunk:
                if line.is_added:
                    new_lines.append(line.value)
                elif line.is_context:
                    new_lines.append(line.value)
                # Skip removed lines

            # Replace the section
            lines[source_start : source_start + source_length] = new_lines

        result = "".join(lines)
        return True, result, None

    except Exception as e:
        return False, None, f"Failed to apply patch: {str(e)}"


def normalize_line_endings(content: str) -> str:
    """Normalize line endings to LF.

    Args:
        content: Content with potentially mixed line endings

    Returns:
        Content with normalized line endings
    """
    return content.replace("\r\n", "\n").replace("\r", "\n")
