"""
Telos Memory Manager - Goals and Tasks

This module manages structured goal and task data using JSON Lines format.
All operations are append-only to ensure complete data integrity and auditability.

File Format:
- JSON Lines (.jsonl) with one JSON object per line
- Each entry contains: id, timestamp, type, content, status, tags, etc.
- Timestamps in ISO 8601 format with timezone
- Human-readable and machine-parseable

File Location:
- Goals and tasks stored in: ~/.assistant/memory/telos.jsonl

Data Structure:
- Goals: Long-term objectives with status tracking
- Tasks: Specific actions, optionally linked to goals
- Status Updates: Separate entries for status changes (append-only)

Key Classes:
- Goal: Dataclass for goal entries
- Task: Dataclass for task entries
- TelosManager: Main interface for goal/task operations

Append-Only Design:
- Never modifies or deletes existing entries
- Status changes create new "status_update" entries
- Complete audit trail of all changes
- Data recovery possible from file inspection

Validation:
- All entries validated on read and write
- Type checking and format validation
- Required field enforcement
- Timestamp format validation

Usage Patterns:
    # Initialize manager
    telos = TelosManager()

    # Add goal
    goal_id = telos.add_goal("Complete project", tags=["work"])

    # Add linked task
    task_id = telos.add_task("Write docs", parent_goal=goal_id)

    # Update status
    telos.update_status(task_id, "completed")

    # Query data
    goals = telos.get_goals()
    tasks = telos.get_tasks(status_filter="pending")

Performance:
- O(n) for full file reads (acceptable for personal data)
- Efficient filtering and searching
- Minimal memory usage
- Fast append operations

Error Handling:
- File I/O errors logged and handled gracefully
- Validation errors prevent corrupt data
- Partial failures don't corrupt existing data
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path

from config import config
from utils.timestamps import get_current_timestamp, validate_timestamp
from utils import get_logger


logger = get_logger(__name__)


@dataclass
class Goal:
    """Represents a goal in the Telos system."""
    id: str
    timestamp: str
    type: str = "goal"
    content: str = ""
    status: str = "active"  # active, completed, cancelled
    tags: Optional[List[str]] = None
    priority: str = "medium"  # low, medium, high
    due_date: Optional[str] = None
    parent_goal: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class Task:
    """Represents a task in the Telos system."""
    id: str
    timestamp: str
    type: str = "task"
    content: str = ""
    status: str = "pending"  # pending, in_progress, completed, cancelled
    tags: Optional[List[str]] = None
    priority: str = "medium"  # low, medium, high
    due_date: Optional[str] = None
    parent_goal: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class TelosError(Exception):
    """Telos-specific errors."""
    pass


class TelosManager:
    """Manager for Telos goals and tasks using append-only JSONL files."""

    def __init__(self, memory_dir: Optional[str] = None):
        """
        Initialize the Telos manager.

        Args:
            memory_dir: Directory for memory files (uses config if None)
        """
        self.memory_dir = Path(memory_dir or config.memory_dir)
        self.telos_file = self.memory_dir / "telos.jsonl"
        self._ensure_memory_dir()

    def _ensure_memory_dir(self) -> None:
        """Ensure the memory directory exists."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _validate_entry(self, entry: Dict[str, Any]) -> None:
        """
        Validate a Telos entry.

        Args:
            entry: Entry dictionary to validate

        Raises:
            TelosError: If entry is invalid
        """
        # Required fields differ by type
        if entry['type'] in ['goal', 'task']:
            required_fields = ['id', 'timestamp', 'type', 'content']
        elif entry['type'] == 'status_update':
            required_fields = ['id', 'timestamp', 'type', 'target_id', 'new_status', 'target_type']
        else:
            required_fields = ['id', 'timestamp', 'type', 'content']  # fallback

        for field in required_fields:
            if field not in entry:
                raise TelosError(f"Missing required field: {field}")

        if not validate_timestamp(entry['timestamp']):
            raise TelosError(f"Invalid timestamp format: {entry['timestamp']}")

        if entry['type'] not in ['goal', 'task', 'status_update']:
            raise TelosError(f"Invalid type: {entry['type']}. Must be 'goal', 'task', or 'status_update'")

        # Validate status for goals and tasks
        if entry['type'] in ['goal', 'task']:
            if entry['type'] == 'goal':
                valid_statuses = ['active', 'completed', 'cancelled']
            else:  # task
                valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']

            if entry.get('status') not in valid_statuses:
                raise TelosError(f"Invalid status for {entry['type']}: {entry.get('status')}")

        # Validate status_update specific fields
        elif entry['type'] == 'status_update':
            if entry['target_type'] not in ['goal', 'task']:
                raise TelosError(f"Invalid target_type: {entry['target_type']}")

            # Validate new_status based on target_type
            if entry['target_type'] == 'goal':
                valid_statuses = ['active', 'completed', 'cancelled']
            else:  # task
                valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']

            if entry['new_status'] not in valid_statuses:
                raise TelosError(f"Invalid new_status for {entry['target_type']}: {entry['new_status']}")

    def _append_entry(self, entry: Dict[str, Any]) -> None:
        """
        Append an entry to the Telos file.

        Args:
            entry: Entry dictionary to append
        """
        self._validate_entry(entry)

        with open(self.telos_file, 'a', encoding='utf-8') as f:
            json.dump(entry, f, ensure_ascii=False)
            f.write('\n')

        logger.info(f"Appended {entry['type']} entry: {entry['id']}")

    def add_goal(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        priority: str = "medium",
        due_date: Optional[str] = None
    ) -> str:
        """
        Add a new goal.

        Args:
            content: Goal description
            tags: Optional list of tags
            priority: Priority level (low, medium, high)
            due_date: Optional due date (ISO 8601 format)

        Returns:
            Goal ID
        """
        goal_id = f"goal_{get_current_timestamp().replace(':', '').replace('-', '').replace('.', '')}"

        goal = Goal(
            id=goal_id,
            timestamp=get_current_timestamp(),
            content=content,
            tags=tags or [],
            priority=priority,
            due_date=due_date
        )

        self._append_entry(asdict(goal))
        return goal_id

    def add_task(
        self,
        content: str,
        parent_goal: Optional[str] = None,
        tags: Optional[List[str]] = None,
        priority: str = "medium",
        due_date: Optional[str] = None
    ) -> str:
        """
        Add a new task.

        Args:
            content: Task description
            parent_goal: Optional parent goal ID
            tags: Optional list of tags
            priority: Priority level (low, medium, high)
            due_date: Optional due date (ISO 8601 format)

        Returns:
            Task ID
        """
        task_id = f"task_{get_current_timestamp().replace(':', '').replace('-', '').replace('.', '')}"

        task = Task(
            id=task_id,
            timestamp=get_current_timestamp(),
            content=content,
            parent_goal=parent_goal,
            tags=tags or [],
            priority=priority,
            due_date=due_date
        )

        self._append_entry(asdict(task))
        return task_id

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """
        Get all Telos entries.

        Returns:
            List of entry dictionaries
        """
        if not self.telos_file.exists():
            return []

        entries = []
        with open(self.telos_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    self._validate_entry(entry)  # Validate on read
                    entries.append(entry)
                except (json.JSONDecodeError, TelosError) as e:
                    logger.warning(f"Skipping invalid entry at line {line_num}: {e}")
                    continue

        return entries

    def get_goals(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get goals, optionally filtered by status.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of goal dictionaries
        """
        entries = self.get_all_entries()
        goals = [e for e in entries if e['type'] == 'goal']

        if status_filter:
            goals = [g for g in goals if g.get('status') == status_filter]

        return goals

    def get_tasks(self, status_filter: Optional[str] = None, parent_goal: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get tasks, optionally filtered by status and/or parent goal.

        Args:
            status_filter: Optional status to filter by
            parent_goal: Optional parent goal ID to filter by

        Returns:
            List of task dictionaries
        """
        entries = self.get_all_entries()
        tasks = [e for e in entries if e['type'] == 'task']

        if status_filter:
            tasks = [t for t in tasks if t.get('status') == status_filter]

        if parent_goal:
            tasks = [t for t in tasks if t.get('parent_goal') == parent_goal]

        return tasks

    def update_status(self, entry_id: str, new_status: str) -> bool:
        """
        Update the status of an entry by creating a status change annotation.

        Args:
            entry_id: ID of the entry to update
            new_status: New status value

        Returns:
            True if update was recorded, False if entry not found
        """
        # Find the entry
        entries = self.get_all_entries()
        entry = next((e for e in entries if e['id'] == entry_id), None)

        if not entry:
            return False

        # Validate new status
        if entry['type'] == 'goal':
            valid_statuses = ['active', 'completed', 'cancelled']
        else:  # task
            valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']

        if new_status not in valid_statuses:
            raise TelosError(f"Invalid status for {entry['type']}: {new_status}")

        # Create status update entry
        status_update = {
            'id': f"update_{entry_id}_{get_current_timestamp().replace(':', '').replace('-', '').replace('.', '')}",
            'timestamp': get_current_timestamp(),
            'type': 'status_update',
            'target_id': entry_id,
            'old_status': entry.get('status'),
            'new_status': new_status,
            'target_type': entry['type']
        }

        self._append_entry(status_update)
        return True