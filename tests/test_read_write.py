"""Tests for file reading and writing."""

from pathlib import Path

import pytest

from pitcrew.tools.read_write import ReadWrite


def test_read_file(test_project):
    """Test reading a file."""
    rw = ReadWrite(test_project)

    success, content, error = rw.read("src/main.py")

    assert success
    assert "def hello()" in content
    assert error is None


def test_read_nonexistent_file(test_project):
    """Test reading a nonexistent file."""
    rw = ReadWrite(test_project)

    success, content, error = rw.read("nonexistent.py")

    assert not success
    assert content is None
    assert "not found" in error.lower()


def test_write_file(test_project):
    """Test writing a file."""
    rw = ReadWrite(test_project)

    success, error = rw.write("new_file.py", "print('hello')\n")

    assert success
    assert error is None
    assert (test_project / "new_file.py").exists()

    # Verify content
    success, content, _ = rw.read("new_file.py")
    assert "print('hello')" in content


def test_write_creates_directories(test_project):
    """Test that write creates parent directories."""
    rw = ReadWrite(test_project)

    success, error = rw.write("deep/nested/file.txt", "content")

    assert success
    assert (test_project / "deep" / "nested" / "file.txt").exists()


def test_snapshot_and_restore(test_project):
    """Test snapshot and restore functionality."""
    rw = ReadWrite(test_project)

    # Get original content
    original_content = (test_project / "src" / "main.py").read_text()

    # Create snapshot of original state
    success, snapshot_id, error = rw.create_snapshot(["src/main.py"])
    assert success

    # Modify file
    rw.write("src/main.py", "new modified content")

    # Verify file was modified
    success, content, _ = rw.read("src/main.py")
    assert "new modified content" in content

    # Restore snapshot
    success, error = rw.restore_snapshot(snapshot_id)
    assert success

    # Verify content restored
    success, content, _ = rw.read("src/main.py")
    assert content == original_content


def test_path_safety(test_project):
    """Test that paths outside project root are rejected."""
    rw = ReadWrite(test_project)

    # Try to read outside project
    success, content, error = rw.read("../../etc/passwd")

    assert not success
    assert "outside project root" in error.lower()
