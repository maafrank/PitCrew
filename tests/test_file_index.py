"""Tests for file indexing."""

import pytest

from pitcrew.tools.file_index import FileIndex
from pitcrew.utils.ignore import IgnoreRules


def test_build_index(test_project):
    """Test building file index."""
    rules = IgnoreRules(test_project)
    indexer = FileIndex(test_project, rules)

    snapshot = indexer.build()

    assert snapshot.summary["total_files"] > 0
    assert "python" in snapshot.summary["languages"]

    # Check that some expected files are indexed
    paths = [f["path"] for f in snapshot.files]
    assert "src/main.py" in paths
    assert "README.md" in paths


def test_ignore_rules_applied(test_project):
    """Test that ignore rules are applied during indexing."""
    # Create some files that should be ignored
    (test_project / "__pycache__").mkdir()
    (test_project / "__pycache__" / "module.pyc").write_text("bytecode")

    rules = IgnoreRules(test_project)
    indexer = FileIndex(test_project, rules)

    snapshot = indexer.build()

    paths = [f["path"] for f in snapshot.files]
    assert "__pycache__/module.pyc" not in paths


def test_language_detection(test_project):
    """Test language detection."""
    # Create files with different extensions
    (test_project / "script.js").write_text("console.log('hello');")
    (test_project / "data.json").write_text('{"key": "value"}')

    rules = IgnoreRules(test_project)
    indexer = FileIndex(test_project, rules)

    snapshot = indexer.build()

    languages = snapshot.summary["languages"]
    assert "python" in languages
    assert "javascript" in languages
    assert "json" in languages


def test_save_and_load_index(test_project):
    """Test saving and loading index from disk."""
    rules = IgnoreRules(test_project)
    indexer = FileIndex(test_project, rules)

    # Build and save
    snapshot1 = indexer.build()
    indexer.save_to_disk(snapshot1)

    # Load
    snapshot2 = indexer.load_from_disk()

    assert snapshot2 is not None
    assert snapshot2.summary["total_files"] == snapshot1.summary["total_files"]
