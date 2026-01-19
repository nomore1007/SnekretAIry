"""
Logging configuration for the personal assistant.

Provides structured logging with appropriate levels and output formatting.
"""

import logging
import sys
from typing import Optional

try:
    from config import config
except ImportError:
    # Fallback for when config is not available
    config = None


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    name: str = "assistant"
) -> logging.Logger:
    """
    Set up logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        name: Logger name

    Returns:
        Configured logger instance
    """
    # Use config values if not provided
    if level is None:
        level = config.log_level if config else 'INFO'
    if log_file is None:
        log_file = config.log_file if config else None

    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (OSError, IOError) as e:
            # Log to console if file logging fails
            logger.warning(f"Failed to set up file logging to {log_file}: {e}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Module or component name

    Returns:
        Logger instance
    """
    return logging.getLogger(f"assistant.{name}")