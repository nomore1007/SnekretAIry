"""
Proposal engine for interpreting LLM suggestions into structured change proposals.

Creates validated, user-approved change proposals from LLM output.
"""

import json
import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from config import config
from memory import TelosManager, JournalManager
from utils import get_logger


logger = get_logger(__name__)


@dataclass
class TelosProposal:
    """Proposal for a Telos (goal/task) change."""
    action: str  # 'add_goal', 'add_task', 'update_status'
    content: Optional[str] = None
    goal_id: Optional[str] = None
    task_id: Optional[str] = None
    new_status: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class JournalProposal:
    """Proposal for a Journal entry change."""
    action: str  # 'add_entry'
    content: str = ""
    entry_type: str = "reflection"
    tags: Optional[List[str]] = None
    mood: Optional[str] = None
    location: Optional[str] = None
    weather: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class ChangeProposal:
    """Complete change proposal from LLM."""
    proposal_id: str
    timestamp: str
    talaos_proposals: List[TelosProposal]
    journal_proposals: List[JournalProposal]
    reasoning: str
    confidence_score: float  # 0-1, how confident the LLM is
    raw_llm_output: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'proposal_id': self.proposal_id,
            'timestamp': self.timestamp,
            'talaos_proposals': [asdict(p) for p in self.talaos_proposals],
            'journal_proposals': [asdict(p) for p in self.journal_proposals],
            'reasoning': self.reasoning,
            'confidence_score': self.confidence_score,
            'raw_llm_output': self.raw_llm_output
        }


class ProposalError(Exception):
    """Proposal-related errors."""
    pass


class ProposalEngine:
    """Engine for creating and validating change proposals from LLM output."""

    def __init__(self, memory_dir: Optional[str] = None):
        """
        Initialize the proposal engine.

        Args:
            memory_dir: Directory for memory files (uses config if None)
        """
        self.memory_dir = memory_dir or config.memory_dir
        self.talaos = TelosManager(self.memory_dir)
        self.journal = JournalManager(self.memory_dir)

    def parse_llm_output(self, llm_output: str, user_query: str) -> ChangeProposal:
        """
        Parse LLM output into a structured change proposal.

        Args:
            llm_output: Raw output from LLM
            user_query: Original user query that prompted this response

        Returns:
            Validated change proposal

        Raises:
            ProposalError: If parsing or validation fails
        """
        logger.info("Parsing LLM output into change proposal")

        # Check if the output contains JSON (marked with ```json)
        json_match = re.search(r'```json\s*\n(.*?)\n\s*```', llm_output, re.DOTALL)
        if json_match:
            try:
                # Extract and parse the JSON part
                json_str = json_match.group(1).strip()
                parsed = json.loads(json_str)
                return self._parse_json_proposal(parsed, llm_output)
            except (json.JSONDecodeError, IndexError) as e:
                logger.warning(f"Failed to parse JSON from response: {e}")
                # Fall back to text parsing

        # Try to parse the entire output as JSON (for simple JSON responses)
        try:
            parsed = json.loads(llm_output)
            return self._parse_json_proposal(parsed, llm_output)
        except json.JSONDecodeError:
            # Fall back to text parsing
            return self._parse_text_proposal(llm_output, user_query)

    def _parse_json_proposal(self, parsed: Dict[str, Any], raw_output: str) -> ChangeProposal:
        """
        Parse a JSON-structured proposal.

        Args:
            parsed: Parsed JSON dictionary
            raw_output: Raw LLM output

        Returns:
            ChangeProposal object
        """
        # Extract basic proposal info
        proposal_id = parsed.get('proposal_id', f"proposal_{datetime.now().isoformat()}")
        reasoning = parsed.get('reasoning', 'No reasoning provided')
        confidence = min(max(float(parsed.get('confidence', 0.5)), 0.0), 1.0)

        # Parse Talaos proposals
        talaos_proposals = []
        for tp_data in parsed.get('talaos_proposals', []):
            try:
                proposal = TelosProposal(**tp_data)
                talaos_proposals.append(proposal)
            except (TypeError, ValueError) as e:
                logger.warning(f"Invalid Talaos proposal: {e}")
                continue

        # Parse Journal proposals
        journal_proposals = []
        for jp_data in parsed.get('journal_proposals', []):
            try:
                proposal = JournalProposal(**jp_data)
                journal_proposals.append(proposal)
            except (TypeError, ValueError) as e:
                logger.warning(f"Invalid Journal proposal: {e}")
                continue

        proposal = ChangeProposal(
            proposal_id=proposal_id,
            timestamp=datetime.now().isoformat(),
            talaos_proposals=talaos_proposals,
            journal_proposals=journal_proposals,
            reasoning=reasoning,
            confidence_score=confidence,
            raw_llm_output=raw_output
        )

        self._validate_proposal(proposal)
        return proposal

    def _parse_text_proposal(self, text_output: str, user_query: str) -> ChangeProposal:
        """
        Parse a text-based proposal.

        Args:
            text_output: Text output from LLM
            user_query: Original user query

        Returns:
            ChangeProposal object
        """
        # Simple text parsing - look for structured content
        talaos_proposals = []
        journal_proposals = []

        # Look for goal/task suggestions
        goal_matches = re.findall(
            r'(?:suggest|add|create).*(?:goal|task).*?["\']([^"\']+)["\']',
            text_output,
            re.IGNORECASE
        )

        for goal_content in goal_matches[:2]:  # Limit to 2 suggestions
            if 'task' in text_output.lower():
                talaos_proposals.append(TelosProposal(
                    action='add_task',
                    content=goal_content.strip(),
                    tags=['suggested']
                ))
            else:
                talaos_proposals.append(TelosProposal(
                    action='add_goal',
                    content=goal_content.strip(),
                    tags=['suggested']
                ))

        # Look for journal/reflection suggestions
        reflection_matches = re.findall(
            r'(?:reflect|journal|note|remember).*?["\']([^"\']+)["\']',
            text_output,
            re.IGNORECASE
        )

        for reflection_content in reflection_matches[:1]:  # Limit to 1 reflection
            journal_proposals.append(JournalProposal(
                action='add_entry',
                content=reflection_content.strip(),
                entry_type='reflection',
                tags=['suggested']
            ))

        # Extract reasoning
        reasoning = self._extract_reasoning(text_output)

        proposal = ChangeProposal(
            proposal_id=f"text_proposal_{datetime.now().isoformat()}",
            timestamp=datetime.now().isoformat(),
            talaos_proposals=talaos_proposals,
            journal_proposals=journal_proposals,
            reasoning=reasoning,
            confidence_score=0.3,  # Lower confidence for text parsing
            raw_llm_output=text_output
        )

        self._validate_proposal(proposal)
        return proposal

    def _extract_reasoning(self, text_output: str) -> str:
        """Extract reasoning from text output."""
        # Look for common reasoning patterns
        reasoning_patterns = [
            r'(?:because|since|reason).*?([^.!?]+[.!?])',
            r'(?:suggest|suggesting).*?([^.!?]+[.!?])',
            r'(?:think|believe|recommend).*?([^.!?]+[.!?])'
        ]

        for pattern in reasoning_patterns:
            matches = re.findall(pattern, text_output, re.IGNORECASE)
            if matches:
                return matches[0].strip()

        # Fallback: first sentence
        sentences = re.split(r'[.!?]+', text_output.strip())
        return sentences[0].strip() if sentences else "No explicit reasoning provided"

    def _validate_proposal(self, proposal: ChangeProposal) -> None:
        """
        Validate a change proposal for safety and correctness.

        Args:
            proposal: Proposal to validate

        Raises:
            ProposalError: If proposal is invalid or unsafe
        """
        # Check confidence score
        if not (0.0 <= proposal.confidence_score <= 1.0):
            raise ProposalError(f"Invalid confidence score: {proposal.confidence_score}")

        # Validate Talaos proposals
        for tp in proposal.talaos_proposals:
            self._validate_talaos_proposal(tp)

        # Validate Journal proposals
        for jp in proposal.journal_proposals:
            self._validate_journal_proposal(jp)

        # Safety checks
        total_changes = len(proposal.talaos_proposals) + len(proposal.journal_proposals)
        if total_changes > 5:
            raise ProposalError(f"Too many changes proposed: {total_changes} (max 5)")

        # Check for any destructive operations (shouldn't happen but be safe)
        for tp in proposal.talaos_proposals:
            if tp.action not in ['add_goal', 'add_task', 'update_status']:
                raise ProposalError(f"Unsupported Talaos action: {tp.action}")

        for jp in proposal.journal_proposals:
            if jp.action not in ['add_entry']:
                raise ProposalError(f"Unsupported Journal action: {jp.action}")

    def _validate_talaos_proposal(self, proposal: TelosProposal) -> None:
        """Validate a single Talaos proposal."""
        if proposal.action not in ['add_goal', 'add_task', 'update_status']:
            raise ProposalError(f"Invalid Talaos action: {proposal.action}")

        if proposal.action in ['add_goal', 'add_task']:
            if not proposal.content or not proposal.content.strip():
                raise ProposalError("Content required for add operations")

        if proposal.action == 'update_status':
            if not proposal.goal_id and not proposal.task_id:
                raise ProposalError("Goal or task ID required for status updates")
            if not proposal.new_status:
                raise ProposalError("New status required for status updates")

            # Validate status values
            if proposal.goal_id:
                valid_statuses = ['active', 'completed', 'cancelled']
            else:
                valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']

            if proposal.new_status not in valid_statuses:
                raise ProposalError(f"Invalid status: {proposal.new_status}")

        if proposal.priority and proposal.priority not in ['low', 'medium', 'high']:
            raise ProposalError(f"Invalid priority: {proposal.priority}")

    def _validate_journal_proposal(self, proposal: JournalProposal) -> None:
        """Validate a single Journal proposal."""
        if proposal.action not in ['add_entry']:
            raise ProposalError(f"Invalid Journal action: {proposal.action}")

        if not proposal.content or not proposal.content.strip():
            raise ProposalError("Content required for journal entries")

        if proposal.entry_type not in ['reflection', 'gratitude', 'learning', 'goal_review', 'planning']:
            raise ProposalError(f"Invalid entry type: {proposal.entry_type}")

    def present_proposal(self, proposal: ChangeProposal) -> str:
        """
        Format a proposal for user presentation.

        Args:
            proposal: Proposal to format

        Returns:
            Human-readable proposal text
        """
        lines = []
        lines.append("🤖 AI Assistant Proposal")
        lines.append("=" * 50)
        lines.append(f"Confidence: {proposal.confidence_score:.1%}")
        lines.append("")
        lines.append(f"Reasoning: {proposal.reasoning}")
        lines.append("")

        if proposal.talaos_proposals:
            lines.append("📋 Proposed Changes to Goals & Tasks:")
            for i, tp in enumerate(proposal.talaos_proposals, 1):
                if tp.action == 'add_goal':
                    lines.append(f"  {i}. Add goal: \"{tp.content}\"")
                    if tp.tags:
                        lines.append(f"     Tags: {', '.join(tp.tags)}")
                elif tp.action == 'add_task':
                    lines.append(f"  {i}. Add task: \"{tp.content}\"")
                    if tp.tags:
                        lines.append(f"     Tags: {', '.join(tp.tags)}")
                elif tp.action == 'update_status':
                    target = tp.goal_id or tp.task_id
                    lines.append(f"  {i}. Update {tp.goal_id and 'goal' or 'task'} {target} status to: {tp.new_status}")
            lines.append("")

        if proposal.journal_proposals:
            lines.append("📖 Proposed Journal Entries:")
            for i, jp in enumerate(proposal.journal_proposals, 1):
                lines.append(f"  {i}. Add {jp.entry_type}: \"{jp.content[:100]}...\"")
                if jp.tags:
                    lines.append(f"     Tags: {', '.join(jp.tags)}")
            lines.append("")

        lines.append("❓ Do you want to apply these changes? (y/N): ")

        return "\n".join(lines)

    def apply_proposal(self, proposal: ChangeProposal) -> Dict[str, Any]:
        """
        Apply an approved proposal to the memory systems.

        Args:
            proposal: Approved proposal to apply

        Returns:
            Dictionary with results of applied changes
        """
        logger.info(f"Applying proposal {proposal.proposal_id}")

        results = {
            'proposal_id': proposal.proposal_id,
            'applied_at': datetime.now().isoformat(),
            'talaos_changes': [],
            'journal_changes': [],
            'success': True,
            'errors': []
        }

        # Apply Talaos changes
        for tp in proposal.talaos_proposals:
            try:
                if tp.action == 'add_goal':
                    goal_id = self.talaos.add_goal(
                        content=tp.content or "",
                        tags=tp.tags,
                        priority=tp.priority or "medium",
                        due_date=tp.due_date
                    )
                    results['talaos_changes'].append({
                        'action': 'add_goal',
                        'goal_id': goal_id,
                        'content': tp.content
                    })

                elif tp.action == 'add_task':
                    task_id = self.talaos.add_task(
                        content=tp.content or "",
                        parent_goal=tp.goal_id,
                        tags=tp.tags,
                        priority=tp.priority or "medium",
                        due_date=tp.due_date
                    )
                    results['talaos_changes'].append({
                        'action': 'add_task',
                        'task_id': task_id,
                        'content': tp.content
                    })

                elif tp.action == 'update_status':
                    target_id = tp.goal_id or tp.task_id
                    if target_id and tp.new_status:
                        success = self.talaos.update_status(target_id, tp.new_status)
                    else:
                        success = False
                    if success:
                        results['talaos_changes'].append({
                            'action': 'update_status',
                            'target_id': tp.goal_id or tp.task_id,
                            'new_status': tp.new_status
                        })
                    else:
                        results['errors'].append(f"Failed to update status for {tp.goal_id or tp.task_id}")

            except Exception as e:
                results['errors'].append(f"Talaos error: {e}")
                results['success'] = False

        # Apply Journal changes
        for jp in proposal.journal_proposals:
            try:
                if jp.action == 'add_entry':
                    timestamp = self.journal.add_entry(
                        content=jp.content,
                        entry_type=jp.entry_type,
                        tags=jp.tags,
                        mood=jp.mood,
                        location=jp.location,
                        weather=jp.weather
                    )
                    results['journal_changes'].append({
                        'action': 'add_entry',
                        'timestamp': timestamp,
                        'type': jp.entry_type,
                        'content_preview': jp.content[:50] + "..."
                    })

            except Exception as e:
                results['errors'].append(f"Journal error: {e}")
                results['success'] = False

        logger.info(f"Proposal application complete: {len(results['talaos_changes'])} Talaos, {len(results['journal_changes'])} Journal changes")
        return results