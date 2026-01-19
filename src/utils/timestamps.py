"""
Timestamp utilities for the personal assistant.

Provides ISO 8601 timestamping and time zone handling.
"""

import datetime
from typing import Optional


def get_current_timestamp() -> str:
    """
    Get current timestamp in ISO 8601 format with timezone.

    Returns:
        ISO 8601 formatted timestamp string
    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def parse_timestamp(timestamp_str: str) -> datetime.datetime:
    """
    Parse an ISO 8601 timestamp string.

    Args:
        timestamp_str: ISO 8601 formatted timestamp

    Returns:
        datetime object

    Raises:
        ValueError: If timestamp format is invalid
    """
    try:
        # Try parsing with timezone info first
        return datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except ValueError:
        # Fallback to naive datetime (assume UTC)
        dt = datetime.datetime.fromisoformat(timestamp_str)
        return dt.replace(tzinfo=datetime.timezone.utc)


def format_timestamp(dt: datetime.datetime) -> str:
    """
    Format a datetime object as ISO 8601 string.

    Args:
        dt: datetime object to format

    Returns:
        ISO 8601 formatted string
    """
    if dt.tzinfo is None:
        # Assume UTC if no timezone
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    return dt.isoformat()


def validate_timestamp(timestamp_str: str) -> bool:
    """
    Validate that a string is a valid ISO 8601 timestamp.

    Args:
        timestamp_str: String to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        parse_timestamp(timestamp_str)
        return True
    except ValueError:
        return False