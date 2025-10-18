"""Tests for ignore rules."""

from pathlib import Path

import pytest

from pitcrew.utils.ignore import IgnoreRules


def test_builtin_ignores(test_project):
    """Test that built-in patterns are ignored."""
    rules = IgnoreRules(test_project)

    assert rules.should_ignore(test_project / ".git" / "config")
    assert rules.should_ignore(test_project / "node_modules" / "package")
    assert rules.should_ignore(test_project / "__pycache__" / "module.pyc")
    assert rules.should_ignore(test_project / ".bot" / "index.json")


def test_gitignore_respected(test_project):
    """Test that .gitignore is respected."""
    # Create .gitignore
    (test_project / ".gitignore").write_text("*.log\nbuild/\n")

    rules = IgnoreRules(test_project)

    assert rules.should_ignore(test_project / "debug.log")
    assert rules.should_ignore(test_project / "build" / "output")
    assert not rules.should_ignore(test_project / "src" / "main.py")


def test_codebotignore_respected(test_project):
    """Test that .codebotignore is respected."""
    # Create .codebotignore
    (test_project / ".codebotignore").write_text("*.tmp\ndata/\n")

    rules = IgnoreRules(test_project)

    assert rules.should_ignore(test_project / "temp.tmp")
    assert rules.should_ignore(test_project / "data" / "file.txt")
    assert not rules.should_ignore(test_project / "src" / "main.py")


def test_normal_files_not_ignored(test_project):
    """Test that normal files are not ignored."""
    rules = IgnoreRules(test_project)

    assert not rules.should_ignore(test_project / "src" / "main.py")
    assert not rules.should_ignore(test_project / "README.md")
    assert not rules.should_ignore(test_project / "tests" / "test_main.py")
