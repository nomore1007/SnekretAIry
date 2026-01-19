"""
Journal Memory Manager - Personal Reflections

This module manages personal reflection entries using Markdown with YAML frontmatter.
Designed for narrative content with structured metadata in an append-only format.

File Format:
- Markdown (.md) with YAML frontmatter blocks
- Each entry separated by visual dividers (=====...)
- Frontmatter contains: timestamp, type, tags, mood, location, etc.
- Content supports full Markdown formatting

Entry Types:
- reflection: General thoughts and observations
- gratitude: Things to be thankful for
- learning: New knowledge or skills acquired
- goal_review: Progress assessment on goals
- planning: Future planning and strategy

Frontmatter Structure:
---
timestamp: '2024-01-19T10:30:00+00:00'
type: reflection
tags: [work, progress]
mood: productive
location: home office
---

Append-Only Design:
- New entries always appended to end of file
- Never modifies existing content
- Visual separators between entries
- Complete chronological history preserved

Search and Filtering:
- Full-text search across content and metadata
- Type-based filtering (reflection, gratitude, etc.)
- Tag-based filtering with AND logic
- Date range filtering
- Combined multi-criteria searches

Usage Patterns:
    # Initialize manager
    journal = JournalManager()

    # Add reflection
    timestamp = journal.add_entry(
        "Made great progress on the project today",
        entry_type="reflection",
        tags=["work", "progress"],
        mood="accomplished"
    )

    # Search entries
    recent = journal.get_recent_entries(limit=5)
    work_entries = journal.search_entries(
        query="project",
        tags=["work"],
        date_from="2024-01-01"
    )

Validation:
- Required fields: timestamp, type, content
- Type validation against allowed entry types
- Timestamp format validation
- Content non-emptiness checks

Performance:
- Efficient for append operations
- O(n) for full file reads and searches
- Optimized for personal-scale data (hundreds to thousands of entries)
- Minimal parsing overhead

Integration:
- Works seamlessly with context builder for AI queries
- Supports rich metadata for intelligent filtering
- Compatible with external Markdown viewers/editors
- Human-readable format for emergency access
"""

import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import yaml

from config import config
from utils.timestamps import get_current_timestamp, validate_timestamp
from utils import get_logger


logger = get_logger(__name__)


@dataclass
class JournalEntry:
    """Represents a journal entry."""
    timestamp: str
    type: str = "reflection"
    content: str = ""
    tags: Optional[List[str]] = None
    mood: Optional[str] = None
    location: Optional[str] = None
    weather: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class JournalError(Exception):
    """Journal-specific errors."""
    pass


class JournalManager:
    """Manager for journal entries using append-only Markdown files with YAML frontmatter."""

    def __init__(self, memory_dir: Optional[str] = None):
        """
        Initialize the journal manager.

        Args:
            memory_dir: Directory for memory files (uses config if None)
        """
        self.memory_dir = Path(memory_dir or config.memory_dir)
        self.journal_file = self.memory_dir / "journal.md"
        self._ensure_memory_dir()

    def _ensure_memory_dir(self) -> None:
        """Ensure the memory directory exists."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """
        Parse YAML frontmatter from content.

        Args:
            content: Content with potential frontmatter

        Returns:
            Tuple of (frontmatter dict, content without frontmatter)
        """
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
        if not frontmatter_match:
            return {}, content

        try:
            frontmatter = yaml.safe_load(frontmatter_match.group(1))
            if not isinstance(frontmatter, dict):
                frontmatter = {}
        except yaml.YAMLError:
            frontmatter = {}

        return frontmatter, frontmatter_match.group(2)

    def _format_entry(self, entry: JournalEntry) -> str:
        """
        Format a journal entry as Markdown with YAML frontmatter.

        Args:
            entry: Journal entry to format

        Returns:
            Formatted entry string
        """
        # Prepare frontmatter
        frontmatter = {
            'timestamp': entry.timestamp,
            'type': entry.type,
            'tags': entry.tags
        }

        # Add optional fields if they exist
        if entry.mood:
            frontmatter['mood'] = entry.mood
        if entry.location:
            frontmatter['location'] = entry.location
        if entry.weather:
            frontmatter['weather'] = entry.weather

        # Format as YAML
        frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)

        # Combine frontmatter and content
        formatted = f"---\n{frontmatter_yaml}---\n\n{entry.content}\n\n"

        return formatted

    def _validate_entry(self, entry: JournalEntry) -> None:
        """
        Validate a journal entry.

        Args:
            entry: Entry to validate

        Raises:
            JournalError: If entry is invalid
        """
        if not validate_timestamp(entry.timestamp):
            raise JournalError(f"Invalid timestamp: {entry.timestamp}")

        if entry.type not in ['reflection', 'gratitude', 'learning', 'goal_review', 'planning']:
            raise JournalError(f"Invalid entry type: {entry.type}")

        if not entry.content.strip():
            raise JournalError("Entry content cannot be empty")

    def _append_entry(self, entry: JournalEntry) -> None:
        """
        Append an entry to the journal file.

        Args:
            entry: Journal entry to append
        """
        self._validate_entry(entry)

        formatted_entry = self._format_entry(entry)

        with open(self.journal_file, 'a', encoding='utf-8') as f:
            f.write(formatted_entry)
            f.write('\n' + '='*50 + '\n\n')  # Separator between entries

        logger.info(f"Appended journal entry: {entry.type} at {entry.timestamp}")

    def add_entry(
        self,
        content: str,
        entry_type: str = "reflection",
        tags: Optional[List[str]] = None,
        mood: Optional[str] = None,
        location: Optional[str] = None,
        weather: Optional[str] = None
    ) -> str:
        """
        Add a new journal entry.

        Args:
            content: Entry content (Markdown supported)
            entry_type: Type of entry (reflection, gratitude, learning, etc.)
            tags: Optional list of tags
            mood: Optional mood indicator
            location: Optional location
            weather: Optional weather description

        Returns:
            Timestamp of the entry
        """
        timestamp = get_current_timestamp()

        entry = JournalEntry(
            timestamp=timestamp,
            type=entry_type,
            content=content,
            tags=tags or [],
            mood=mood,
            location=location,
            weather=weather
        )

        self._append_entry(entry)
        return timestamp

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """
        Get all journal entries.

        Returns:
            List of entry dictionaries with frontmatter and content
        """
        if not self.journal_file.exists():
            return []

        entries = []
        try:
            with open(self.journal_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Split by entry separators (==========)
            entry_blocks = re.split(r'\n={50,}\n\n', content.strip())

            for block in entry_blocks:
                if not block.strip():
                    continue

                frontmatter, entry_content = self._parse_frontmatter(block.strip())

                if frontmatter:  # Only include entries with valid frontmatter
                    entry = {
                        'frontmatter': frontmatter,
                        'content': entry_content.strip(),
                        'raw': block.strip()
                    }
                    entries.append(entry)

        except (IOError, OSError) as e:
            logger.error(f"Error reading journal file: {e}")
            return []

        return entries

    def search_entries(
        self,
        query: Optional[str] = None,
        entry_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search journal entries with various filters.

        Args:
            query: Text to search for in content
            entry_type: Filter by entry type
            tags: Filter by tags (entry must have all specified tags)
            date_from: Filter entries from this date (ISO 8601)
            date_to: Filter entries to this date (ISO 8601)

        Returns:
            List of matching entries
        """
        entries = self.get_all_entries()
        filtered_entries = []

        for entry in entries:
            frontmatter = entry['frontmatter']

            # Type filter
            if entry_type and frontmatter.get('type') != entry_type:
                continue

            # Tags filter (entry must contain all specified tags)
            if tags:
                entry_tags = set(frontmatter.get('tags', []))
                query_tags = set(tags)
                if not query_tags.issubset(entry_tags):
                    continue

            # Date filters
            if date_from or date_to:
                try:
                    entry_date = frontmatter.get('timestamp', '')[:10]  # YYYY-MM-DD

                    if date_from and entry_date < date_from[:10]:
                        continue
                    if date_to and entry_date > date_to[:10]:
                        continue
                except (KeyError, IndexError):
                    continue

            # Text search
            if query:
                search_text = entry['content'].lower() + ' ' + ' '.join(frontmatter.get('tags', [])).lower()
                if query.lower() not in search_text:
                    continue

            filtered_entries.append(entry)

        return filtered_entries

    def get_recent_entries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent journal entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent entries (newest first)
        """
        entries = self.get_all_entries()

        # Sort by timestamp (newest first)
        try:
            entries.sort(key=lambda e: e['frontmatter']['timestamp'], reverse=True)
        except (KeyError, TypeError):
            # If sorting fails, return as-is
            pass

        return entries[:limit]