"""Constants and default values for PitCrew."""

import re
from pathlib import Path

# Default model configuration
DEFAULT_MODEL = "anthropic:claude-sonnet-4-5"

# Execution defaults
DEFAULT_EXEC_TIMEOUT = 45  # seconds
DEFAULT_EXEC_NET_POLICY = "deny"

# File size limits (in MB)
DEFAULT_MAX_READ_MB = 8
DEFAULT_MAX_WRITE_MB = 2

# Built-in ignore patterns
BUILTIN_IGNORES = [
    # Version control and project metadata
    ".git/",
    ".gitignore",
    ".gitattributes",
    ".github/",

    # PitCrew internal
    ".pitcrew/",

    # Python
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".Python",
    "*.egg-info/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".tox/",
    ".coverage",
    "htmlcov/",

    # Virtual environments
    "venv/",
    "env/",
    ".venv/",
    "ENV/",

    # Build artifacts
    "dist/",
    "build/",
    "*.so",
    "*.dylib",
    "*.dll",

    # JavaScript/Node
    "node_modules/",
    "package-lock.json",
    "yarn.lock",

    # IDE and editor files
    ".DS_Store",
    "*.swp",
    "*.swo",
    ".vscode/",
    ".idea/",
    "*.sublime-*",

    # Logs and databases
    "*.log",
    "*.sqlite",
    "*.db",
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

# Model descriptors - Anthropic Claude models only
SUPPORTED_MODELS = {
    # Claude Sonnet 4.5 - Latest flagship model (best for coding and agents)
    "anthropic:claude-sonnet-4-5": {
        "provider": "anthropic",
        "name": "claude-sonnet-4-5-20250929",
        "max_output_tokens": 8192,
    },
    # Claude Haiku 4.5 - Fast and cost-effective
    "anthropic:claude-haiku-4-5": {
        "provider": "anthropic",
        "name": "claude-haiku-4-5-20251001",
        "max_output_tokens": 8192,
    },
    # Claude Opus 4.1 - Most capable for complex reasoning
    "anthropic:claude-opus-4-1": {
        "provider": "anthropic",
        "name": "claude-opus-4-1-20250805",
        "max_output_tokens": 8192,
    },
}
