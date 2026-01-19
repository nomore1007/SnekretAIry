"""
Memory mutation engine for safe change application.

Handles approved changes with full audit trails and status tracking.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from config import config
from memory import TelosManager, JournalManager
from proposals import ChangeProposal, TelosProposal, JournalProposal
from utils import get_logger, get_current_timestamp


logger = get_logger(__name__)


@dataclass
class ChangeRecord:
    """Record of an applied change."""
    change_id: str
    timestamp: str
    proposal_id: str
    change_type: str  # 'talaos' or 'journal'
    action: str
    target_id: Optional[str]
    description: str
    success: bool
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return asdict(self)


class MutationEngine:
    """Engine for applying changes with comprehensive audit trails."""

    def __init__(self, memory_dir: Optional[str] = None):
        """
        Initialize the mutation engine.

        Args:
            memory_dir: Directory for memory files (uses config if None)
        """
        self.memory_dir = Path(memory_dir or config.memory_dir)
        self.talaos = TelosManager(str(self.memory_dir))
        self.journal = JournalManager(str(self.memory_dir))
        self.changes_file = self.memory_dir / "changes.jsonl"

    def apply_changes_with_audit(
        self,
        proposal: ChangeProposal,
        user_approval: bool = True
    ) -> Dict[str, Any]:
        """
        Apply changes from a proposal with full audit trail.

        Args:
            proposal: Approved proposal to apply
            user_approval: Whether user approved (for audit)

        Returns:
            Comprehensive results with audit information
        """
        if not user_approval:
            raise ValueError("Changes cannot be applied without user approval")

        logger.info(f"Applying proposal {proposal.proposal_id} with audit trail")

        results = {
            'proposal_id': proposal.proposal_id,
            'applied_at': get_current_timestamp(),
            'user_approved': user_approval,
            'changes_applied': [],
            'audit_records': [],
            'success': True,
            'summary': self._create_change_summary(proposal)
        }

        change_counter = 0

        # Apply Talaos changes
        for tp in proposal.talaos_proposals:
            change_counter += 1
            change_record = self._apply_talaos_change(tp, proposal.proposal_id, change_counter)
            results['changes_applied'].append(change_record)
            results['audit_records'].append(change_record)

        # Apply Journal changes
        for jp in proposal.journal_proposals:
            change_counter += 1
            change_record = self._apply_journal_change(jp, proposal.proposal_id, change_counter)
            results['changes_applied'].append(change_record)
            results['audit_records'].append(change_record)

        # Check for any failures
        failed_changes = [r for r in results['changes_applied'] if not r['success']]
        if failed_changes:
            results['success'] = False
            logger.warning(f"Some changes failed: {len(failed_changes)}")

        # Write audit trail
        self._write_audit_records(results['audit_records'])

        logger.info(f"Change application complete: {len(results['changes_applied'])} changes, success={results['success']}")
        return results

    def _apply_talaos_change(
        self,
        proposal: TelosProposal,
        proposal_id: str,
        change_number: int
    ) -> Dict[str, Any]:
        """
        Apply a single Talaos change with audit record.

        Args:
            proposal: Talaos proposal to apply
            proposal_id: Parent proposal ID
            change_number: Sequential change number

        Returns:
            Change record dictionary
        """
        change_id = f"{proposal_id}_talaos_{change_number}"
        timestamp = get_current_timestamp()

        record = {
            'change_id': change_id,
            'timestamp': timestamp,
            'proposal_id': proposal_id,
            'change_type': 'talaos',
            'action': proposal.action,
            'target_id': None,
            'description': '',
            'success': False,
            'details': {},
            'error': None
        }

        try:
            logger.debug(f"Applying Talaos change: action={proposal.action}, content={proposal.content}, goal_id={proposal.goal_id}")

            if proposal.action == 'add_goal':
                goal_id = self.talaos.add_goal(
                    content=proposal.content or "",
                    tags=proposal.tags,
                    priority=proposal.priority or "medium",
                    due_date=proposal.due_date
                )
                record.update({
                    'target_id': goal_id,
                    'description': f"Added goal: {proposal.content}",
                    'success': True,
                    'details': {'goal_id': goal_id, 'content': proposal.content, 'tags': proposal.tags}
                })

            elif proposal.action == 'add_task':
                task_id = self.talaos.add_task(
                    content=proposal.content or "",
                    parent_goal=proposal.goal_id,
                    tags=proposal.tags,
                    priority=proposal.priority or "medium",
                    due_date=proposal.due_date
                )
                record.update({
                    'target_id': task_id,
                    'description': f"Added task: {proposal.content}",
                    'success': True,
                    'details': {'task_id': task_id, 'content': proposal.content, 'parent_goal': proposal.goal_id}
                })

            elif proposal.action == 'update_status':
                target_id = proposal.goal_id or proposal.task_id
                if target_id and proposal.new_status:
                    success = self.talaos.update_status(target_id, proposal.new_status)
                    record.update({
                        'target_id': target_id,
                        'description': f"Updated status to {proposal.new_status}",
                        'success': success,
                        'details': {'target_id': target_id, 'new_status': proposal.new_status}
                    })
                else:
                    record.update({
                        'success': False,
                        'error': 'Missing target_id or new_status'
                    })

        except Exception as e:
            record.update({
                'success': False,
                'error': str(e)
            })
            logger.error(f"Failed to apply Talaos change {change_id}: {e}")

        return record

    def _apply_journal_change(
        self,
        proposal: JournalProposal,
        proposal_id: str,
        change_number: int
    ) -> Dict[str, Any]:
        """
        Apply a single Journal change with audit record.

        Args:
            proposal: Journal proposal to apply
            proposal_id: Parent proposal ID
            change_number: Sequential change number

        Returns:
            Change record dictionary
        """
        change_id = f"{proposal_id}_journal_{change_number}"
        timestamp = get_current_timestamp()

        record = {
            'change_id': change_id,
            'timestamp': timestamp,
            'proposal_id': proposal_id,
            'change_type': 'journal',
            'action': proposal.action,
            'target_id': None,
            'description': '',
            'success': False,
            'details': {},
            'error': None
        }

        try:
            if proposal.action == 'add_entry':
                entry_timestamp = self.journal.add_entry(
                    content=proposal.content,
                    entry_type=proposal.entry_type,
                    tags=proposal.tags,
                    mood=proposal.mood,
                    location=proposal.location,
                    weather=proposal.weather
                )
                record.update({
                    'target_id': entry_timestamp,
                    'description': f"Added {proposal.entry_type} entry",
                    'success': True,
                    'details': {
                        'timestamp': entry_timestamp,
                        'type': proposal.entry_type,
                        'content_preview': proposal.content[:50] + "...",
                        'tags': proposal.tags
                    }
                })

        except Exception as e:
            record.update({
                'success': False,
                'error': str(e)
            })
            logger.error(f"Failed to apply Journal change {change_id}: {e}")

        return record

    def _create_change_summary(self, proposal: ChangeProposal) -> str:
        """Create a human-readable summary of the changes."""
        parts = []
        if proposal.talaos_proposals:
            parts.append(f"{len(proposal.talaos_proposals)} goal/task changes")
        if proposal.journal_proposals:
            parts.append(f"{len(proposal.journal_proposals)} journal entries")

        if not parts:
            return "No changes"

        return ", ".join(parts)

    def _write_audit_records(self, records: List[Dict[str, Any]]) -> None:
        """
        Write audit records to the changes file.

        Args:
            records: List of change records to write
        """
        for record in records:
            try:
                with open(self.changes_file, 'a', encoding='utf-8') as f:
                    json.dump(record, f, ensure_ascii=False)
                    f.write('\n')
            except Exception as e:
                logger.error(f"Failed to write audit record {record['change_id']}: {e}")

    def get_change_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get the audit history of applied changes.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of change records (newest first)
        """
        if not self.changes_file.exists():
            return []

        records = []
        try:
            with open(self.changes_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            records.append(record)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Error reading change history: {e}")
            return []

        # Sort by timestamp (newest first) and limit
        records.sort(key=lambda r: r.get('timestamp', ''), reverse=True)
        return records[:limit]

    def get_proposal_history(self) -> List[str]:
        """
        Get list of applied proposal IDs.

        Returns:
            List of proposal IDs that have been applied
        """
        records = self.get_change_history()
        proposal_ids = set()
        for record in records:
            proposal_ids.add(record.get('proposal_id'))

        return sorted(list(proposal_ids), reverse=True)