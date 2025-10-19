"""Constants and default values for PitCrew."""

import re
from pathlib import Path

# Default model configuration
DEFAULT_MODEL = "openai:gpt-4o-mini"

# Execution defaults
DEFAULT_EXEC_TIMEOUT = 45  # seconds
DEFAULT_EXEC_NET_POLICY = "deny"

# File size limits (in MB)
DEFAULT_MAX_READ_MB = 8
DEFAULT_MAX_WRITE_MB = 2

# Built-in ignore patterns
BUILTIN_IGNORES = [
    ".git/",
    ".bot/",
    "node_modules/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.egg-info/",
    "venv/",
    "env/",
    ".venv/",
    "dist/",
    "build/",
    ".DS_Store",
    "*.swp",
    "*.swo",
]

# Dangerous command patterns (for executor safety checks)
DANGEROUS_PATTERNS = [
    (re.compile(r'\bsudo\b'), "Use of sudo detected"),
    (re.compile(r'\brm\s+-rf\s+/'), "Recursive delete of root directory"),
    (re.compile(r':\(\)\{.*\|.*\&.*\}'), "Fork bomb pattern detected"),
    (re.compile(r'curl.*\|.*sh'), "Piping curl to shell"),
    (re.compile(r'wget.*\|.*sh'), "Piping wget to shell"),
    (re.compile(r'\bchmod\s+777'), "chmod 777 detected"),
    (re.compile(r'>\s*/dev/sd[a-z]'), "Writing to block device"),
    (re.compile(r'\bdd\s+.*of=/dev/'), "dd to block device"),
]

# Language detection by extension
LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".md": "markdown",
    ".rst": "restructuredtext",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
}

# Model descriptors
SUPPORTED_MODELS = {
    "openai:gpt-4o": {
        "provider": "openai",
        "name": "gpt-4o",
        "max_output_tokens": 4096,
    },
    "openai:gpt-4o-mini": {
        "provider": "openai",
        "name": "gpt-4o-mini",
        "max_output_tokens": 4096,
    },
    "anthropic:claude-3-5-sonnet-20241022": {
        "provider": "anthropic",
        "name": "claude-3-5-sonnet-20241022",
        "max_output_tokens": 8192,
    },
}
