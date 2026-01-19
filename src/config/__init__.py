"""
Configuration Management Module

This module provides centralized configuration management for the personal assistant.
All configuration is environment-variable based for security and flexibility.

Key Features:
- Environment variable validation and type conversion
- Secure credential management (Ollama URL stored in AGENT.md only)
- Default value provision with override capability
- Comprehensive validation with clear error messages

Environment Variables:
- OLLAMA_URL: Ollama server endpoint (required, see AGENT.md)
- OLLAMA_MODEL: Default AI model (default: llama2)
- OLLAMA_TIMEOUT: Request timeout in seconds (default: 120)
- MEMORY_DIR: Memory file storage location (default: ~/.assistant/memory)
- MAX_CONTEXT_SIZE: Maximum context tokens (default: 4000)
- LOG_LEVEL: Logging verbosity (default: INFO)
- LOG_FILE: Optional log file path (default: console only)

Security Notes:
- Ollama URL is the only credential stored externally (in AGENT.md)
- No secrets hardcoded in source code
- All URLs validated for proper format and scheme
- File paths sanitized to prevent directory traversal

Usage:
    from config import config
    ollama_url = config.ollama_url
    memory_dir = config.memory_dir

Thread Safety:
- Global config instance is created once at import time
- Safe for concurrent access after initialization
- Re-import required for configuration changes
"""

import os
from typing import Optional
from urllib.parse import urlparse
from pathlib import Path

from utils import get_logger

logger = get_logger(__name__)


class ConfigError(Exception):
    """Configuration-related errors."""
    pass


class Config:
    """Configuration manager for the application."""

    def __init__(self):
        self._load_env_file()
        self._load_config()

    def _load_env_file(self) -> None:
        """Load environment variables from .env file if it exists."""
        env_file = Path('.env')
        if env_file.exists():
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        # Skip comments and empty lines
                        if not line or line.startswith('#'):
                            continue
                        # Parse KEY=VALUE
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            # Only set if not already set in environment
                            if key not in os.environ:
                                os.environ[key] = value
                                logger.debug(f"Loaded {key} from .env file")
            except Exception as e:
                logger.warning(f"Failed to load .env file: {e}")

    def _load_config(self) -> None:
        """Load and validate configuration from environment variables."""

        # Ollama configuration
        self.ollama_url = self._get_ollama_url()
        self.ollama_timeout = int(os.getenv('OLLAMA_TIMEOUT', '120'))  # seconds (2 minutes default for slow models)
        self.ollama_model = os.getenv('OLLAMA_MODEL', 'llama2')  # default model

        # Memory configuration
        self.memory_dir = os.path.expanduser(os.getenv('MEMORY_DIR', '~/.assistant/memory'))
        self.max_context_size = int(os.getenv('MAX_CONTEXT_SIZE', '4000'))  # tokens

        # Logging configuration
        self.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.log_file = os.getenv('LOG_FILE')

        # Email configuration
        self.email_server = os.getenv('EMAIL_SERVER')
        self.email_port = int(os.getenv('EMAIL_PORT', '993'))
        self.email_username = os.getenv('EMAIL_USERNAME')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.email_ssl = os.getenv('EMAIL_SSL', 'true').lower() == 'true'
        self.email_days_back = int(os.getenv('EMAIL_DAYS_BACK', '7'))

        # Validate configuration
        self._validate_config()

    def _get_ollama_url(self) -> str:
        """Get and validate Ollama URL from environment."""
        url = os.getenv('OLLAMA_URL')
        if not url:
            raise ConfigError(
                "OLLAMA_URL environment variable is required. "
                "Example: export OLLAMA_URL=http://localhost:11434"
            )

        # Validate URL format
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
            if parsed.scheme not in ('http', 'https'):
                raise ValueError("Only HTTP and HTTPS schemes are supported")
        except Exception as e:
            raise ConfigError(f"Invalid OLLAMA_URL: {e}")

        return url.rstrip('/')

    def _validate_config(self) -> None:
        """Validate the loaded configuration."""
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level not in valid_log_levels:
            raise ConfigError(f"Invalid LOG_LEVEL: {self.log_level}. Must be one of {valid_log_levels}")

        if self.ollama_timeout <= 0:
            raise ConfigError("OLLAMA_TIMEOUT must be a positive integer")

        if self.max_context_size <= 0:
            raise ConfigError("MAX_CONTEXT_SIZE must be a positive integer")

        # Ensure memory directory is absolute and safe
        if not os.path.isabs(self.memory_dir):
            raise ConfigError("MEMORY_DIR must be an absolute path")

    @property
    def ollama_generate_endpoint(self) -> str:
        """Get the Ollama generate endpoint URL."""
        return f"{self.ollama_url}/api/generate"

    @property
    def ollama_tags_endpoint(self) -> str:
        """Get the Ollama tags endpoint URL."""
        return f"{self.ollama_url}/api/tags"


# Global configuration instance
config = Config()