"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest

from pitcrew.config import Config
from pitcrew.utils.ignore import IgnoreRules


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_project(temp_dir):
    """Create a test project structure."""
    # Create some files
    (temp_dir / "src").mkdir()
    (temp_dir / "src" / "main.py").write_text("def hello():\n    return 'world'\n")
    (temp_dir / "src" / "utils.py").write_text("def add(a, b):\n    return a + b\n")

    (temp_dir / "tests").mkdir()
    (temp_dir / "tests" / "test_main.py").write_text(
        "def test_hello():\n    from src.main import hello\n    assert hello() == 'world'\n"
    )

    (temp_dir / "README.md").write_text("# Test Project\n")

    yield temp_dir


@pytest.fixture
def mock_config(temp_dir):
    """Create a mock configuration."""
    return Config(
        openai_api_key="test_key",
        default_model="openai:gpt-4o-mini",
    )


@pytest.fixture
def ignore_rules(temp_dir):
    """Create ignore rules for temp directory."""
    return IgnoreRules(temp_dir)
