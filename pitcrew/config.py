"""Configuration loading and management."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from pitcrew.constants import (
    DEFAULT_MODEL,
    DEFAULT_EXEC_TIMEOUT,
    DEFAULT_EXEC_NET_POLICY,
    DEFAULT_MAX_READ_MB,
    DEFAULT_MAX_WRITE_MB,
)


@dataclass
class Config:
    """PitCrew configuration.

    Loads from .env and optionally .bot/config.json
    """

    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    langsmith_api_key: Optional[str] = None
    langsmith_tracing: bool = False
    langsmith_project: str = "PitCrew"

    # Model settings
    default_model: str = DEFAULT_MODEL

    # Execution settings
    exec_timeout: int = DEFAULT_EXEC_TIMEOUT
    exec_net_policy: str = DEFAULT_EXEC_NET_POLICY

    # File limits
    max_read_mb: int = DEFAULT_MAX_READ_MB
    max_write_mb: int = DEFAULT_MAX_WRITE_MB

    # Custom commands (from .bot/config.json)
    custom_commands: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, project_root: Optional[Path] = None) -> "Config":
        """Load configuration from environment and project-specific config.

        Args:
            project_root: Project root directory (for .bot/config.json)

        Returns:
            Config instance
        """
        # Load .env file
        load_dotenv()

        # Create config from environment
        config = cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            langsmith_api_key=os.getenv("LANGSMITH_API_KEY"),
            langsmith_tracing=os.getenv("LANGSMITH_TRACING", "").lower() == "true",
            langsmith_project=os.getenv("LANGSMITH_PROJECT", "PitCrew"),
            default_model=os.getenv("CODEBOT_DEFAULT_MODEL", DEFAULT_MODEL),
            exec_timeout=int(os.getenv("CODEBOT_EXEC_TIMEOUT", DEFAULT_EXEC_TIMEOUT)),
            exec_net_policy=os.getenv("CODEBOT_EXEC_NET", DEFAULT_EXEC_NET_POLICY),
            max_read_mb=int(os.getenv("CODEBOT_MAX_READ_MB", DEFAULT_MAX_READ_MB)),
            max_write_mb=int(os.getenv("CODEBOT_MAX_WRITE_MB", DEFAULT_MAX_WRITE_MB)),
        )

        # Load project-specific config if available
        if project_root:
            bot_config_path = project_root / ".bot" / "config.json"
            if bot_config_path.exists():
                try:
                    with open(bot_config_path) as f:
                        bot_config = json.load(f)
                        config.custom_commands = bot_config.get("commands", {})
                except (json.JSONDecodeError, IOError):
                    pass  # Ignore invalid config

        return config

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if not self.openai_api_key and not self.anthropic_api_key:
            errors.append("No API keys found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY")

        if self.exec_timeout <= 0:
            errors.append("exec_timeout must be positive")

        if self.max_read_mb <= 0:
            errors.append("max_read_mb must be positive")

        if self.max_write_mb <= 0:
            errors.append("max_write_mb must be positive")

        return errors

    def to_dict(self) -> dict:
        """Convert config to dictionary (for logging/display)."""
        return {
            "default_model": self.default_model,
            "exec_timeout": self.exec_timeout,
            "exec_net_policy": self.exec_net_policy,
            "max_read_mb": self.max_read_mb,
            "max_write_mb": self.max_write_mb,
            "custom_commands": self.custom_commands,
            "has_openai_key": bool(self.openai_api_key),
            "has_anthropic_key": bool(self.anthropic_api_key),
        }
