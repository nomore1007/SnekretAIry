"""
Context builder for selecting relevant memory context for LLM input.

Intelligently selects and formats memory data while respecting size limits
and maintaining work/personal context separation.
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

from config import config
from memory import TelosManager, JournalManager
from utils import get_logger


logger = get_logger(__name__)


class ContextBuilder:
    """Builds relevant context from memory for LLM consumption."""

    def __init__(self, memory_dir: Optional[str] = None):
        """
        Initialize the context builder.

        Args:
            memory_dir: Directory for memory files (uses config if None)
        """
        self.memory_dir = memory_dir or config.memory_dir
        self.talaos = TelosManager(self.memory_dir)
        self.journal = JournalManager(self.memory_dir)

        # Context size limits (in characters, conservative estimate)
        self.max_context_size = config.max_context_size * 4  # Rough chars per token
        self.work_context_ratio = 0.6  # 60% for work, 40% for personal
        self.personal_context_ratio = 0.4

    def build_context(
        self,
        query: str,
        context_type: str = "balanced",
        max_entries: int = 10,
        date_range_days: int = 30
    ) -> Dict[str, Any]:
        """
        Build relevant context from memory based on the query.

        Args:
            query: User query or input to find relevant context for
            context_type: Type of context to build ('work', 'personal', 'balanced')
            max_entries: Maximum entries to include per memory type
            date_range_days: How far back to search (days)

        Returns:
            Dictionary with formatted context and metadata
        """
        logger.info(f"Building context for query: {query[:50]}...")

        # Determine date range
        cutoff_date = (datetime.now() - timedelta(days=date_range_days)).isoformat()

        # Search relevant entries
        talaos_entries = self._find_relevant_talaos(query, cutoff_date, max_entries)
        journal_entries = self._find_relevant_journal(query, cutoff_date, max_entries)

        # Separate work vs personal context
        work_context, personal_context = self._separate_work_personal_context(
            talaos_entries, journal_entries, context_type
        )

        # Format for LLM consumption
        formatted_context = self._format_context_for_llm(work_context, personal_context)

        # Ensure size limits
        final_context = self._enforce_size_limits(formatted_context)

        context_info = {
            'query': query,
            'context_type': context_type,
            'date_range_days': date_range_days,
            'total_entries': len(talaos_entries) + len(journal_entries),
            'work_entries': len(work_context['talaos']) + len(work_context['journal']),
            'personal_entries': len(personal_context['talaos']) + len(personal_context['journal']),
            'context_size_chars': len(final_context),
            'estimated_tokens': len(final_context) // 4,  # Rough estimate
            'formatted_context': final_context
        }

        logger.info(
            f"Built context: {context_info['total_entries']} entries, "
            f"{context_info['context_size_chars']} chars, "
            f"{context_info['estimated_tokens']} tokens"
        )

        return context_info

    def _find_relevant_talaos(
        self,
        query: str,
        cutoff_date: str,
        max_entries: int
    ) -> List[Dict[str, Any]]:
        """
        Find relevant Telos entries for the query.

        Args:
            query: Search query
            cutoff_date: ISO date string for cutoff
            max_entries: Maximum entries to return

        Returns:
            List of relevant Telos entries with relevance scores
        """
        # Get recent entries
        all_entries = self.talaos.get_all_entries()

        # Filter by date and calculate relevance
        relevant_entries = []
        query_lower = query.lower()

        for entry in all_entries:
            # Skip old entries
            if entry.get('timestamp', '') < cutoff_date:
                continue

            relevance_score = self._calculate_talaos_relevance(entry, query_lower)

            if relevance_score > 0:
                entry_with_score = dict(entry)
                entry_with_score['_relevance'] = relevance_score
                relevant_entries.append(entry_with_score)

        # Sort by relevance and recency, take top entries
        relevant_entries.sort(key=lambda x: (x['_relevance'], x.get('timestamp', '')), reverse=True)
        return relevant_entries[:max_entries]

    def _find_relevant_journal(
        self,
        query: str,
        cutoff_date: str,
        max_entries: int
    ) -> List[Dict[str, Any]]:
        """
        Find relevant journal entries for the query.

        Args:
            query: Search query
            cutoff_date: ISO date string for cutoff
            max_entries: Maximum entries to return

        Returns:
            List of relevant journal entries with relevance scores
        """
        # Search journal entries
        entries = self.journal.search_entries(
            query=query,
            date_from=cutoff_date[:10]  # YYYY-MM-DD format
        )

        # Add relevance scores
        query_lower = query.lower()
        for entry in entries:
            relevance_score = self._calculate_journal_relevance(entry, query_lower)
            entry['_relevance'] = relevance_score

        # Sort by relevance and recency
        entries.sort(key=lambda x: (x['_relevance'], x['frontmatter'].get('timestamp', '')), reverse=True)
        return entries[:max_entries]

    def _calculate_talaos_relevance(self, entry: Dict[str, Any], query_lower: str) -> float:
        """
        Calculate relevance score for a Telos entry.

        Args:
            entry: Telos entry
            query_lower: Lowercase query string

        Returns:
            Relevance score (0-1, higher is more relevant)
        """
        score = 0.0
        content = entry.get('content', '').lower()
        tags = [tag.lower() for tag in entry.get('tags', [])]

        # Exact phrase match gets highest score
        if query_lower in content:
            score += 1.0

        # Tag matches are very relevant
        for tag in tags:
            if tag in query_lower or query_lower in tag:
                score += 0.8
                break

        # Word matches in content
        query_words = set(query_lower.split())
        content_words = set(re.findall(r'\b\w+\b', content))
        matching_words = query_words.intersection(content_words)

        if matching_words:
            word_score = len(matching_words) / len(query_words)
            score += min(word_score * 0.5, 0.5)  # Cap at 0.5

        # Boost recent entries slightly
        try:
            entry_date = datetime.fromisoformat(entry.get('timestamp', '')[:19])
            days_old = (datetime.now() - entry_date).days
            recency_boost = max(0, 0.1 * (30 - days_old) / 30)  # Boost up to 0.1 for very recent
            score += recency_boost
        except (ValueError, TypeError):
            pass

        return min(score, 1.0)  # Cap at 1.0

    def _calculate_journal_relevance(self, entry: Dict[str, Any], query_lower: str) -> float:
        """
        Calculate relevance score for a journal entry.

        Args:
            entry: Journal entry
            query_lower: Lowercase query string

        Returns:
            Relevance score (0-1, higher is more relevant)
        """
        score = 0.0
        frontmatter = entry.get('frontmatter', {})
        content = entry.get('content', '').lower()
        tags = [tag.lower() for tag in frontmatter.get('tags', [])]

        # Exact phrase match in content
        if query_lower in content:
            score += 1.0

        # Tag matches
        for tag in tags:
            if tag in query_lower or query_lower in tag:
                score += 0.7
                break

        # Type relevance (some types are more relevant than others)
        entry_type = frontmatter.get('type', '')
        type_boosts = {
            'reflection': 0.1,
            'planning': 0.2,
            'goal_review': 0.3,
            'learning': 0.1
        }
        score += type_boosts.get(entry_type, 0)

        # Word matches in content
        query_words = set(query_lower.split())
        content_words = set(re.findall(r'\b\w+\b', content))
        matching_words = query_words.intersection(content_words)

        if matching_words:
            word_score = len(matching_words) / len(query_words)
            score += min(word_score * 0.4, 0.4)  # Cap at 0.4

        # Recency boost
        try:
            entry_date = frontmatter.get('timestamp', '')[:19]
            entry_datetime = datetime.fromisoformat(entry_date)
            days_old = (datetime.now() - entry_datetime).days
            recency_boost = max(0, 0.1 * (30 - days_old) / 30)
            score += recency_boost
        except (ValueError, TypeError, KeyError):
            pass

        return min(score, 1.0)

    def _separate_work_personal_context(
        self,
        talaos_entries: List[Dict[str, Any]],
        journal_entries: List[Dict[str, Any]],
        context_type: str
    ) -> Tuple[Dict[str, List], Dict[str, List]]:
        """
        Separate entries into work and personal context based on tags and content.

        Args:
            talaos_entries: Relevant Telos entries
            journal_entries: Relevant journal entries
            context_type: Type of context ('work', 'personal', 'balanced')

        Returns:
            Tuple of (work_context, personal_context) dictionaries
        """
        work_keywords = {'work', 'professional', 'career', 'project', 'meeting', 'deadline', 'business'}
        personal_keywords = {'personal', 'family', 'health', 'home', 'friends', 'leisure', 'hobby'}

        def classify_entry(entry: Dict[str, Any], is_journal: bool = False) -> str:
            """Classify an entry as work or personal."""
            # Check tags first
            tags = []
            if is_journal:
                tags = entry.get('frontmatter', {}).get('tags', [])
            else:
                tags = entry.get('tags', [])

            tag_text = ' '.join(tags).lower()

            # Check content
            content = ''
            if is_journal:
                content = entry.get('content', '').lower()
            else:
                content = entry.get('content', '').lower()

            # Classification logic
            work_score = sum(1 for keyword in work_keywords if keyword in tag_text or keyword in content)
            personal_score = sum(1 for keyword in personal_keywords if keyword in tag_text or keyword in content)

            if work_score > personal_score:
                return 'work'
            elif personal_score > work_score:
                return 'personal'
            else:
                return 'neutral'  # Could go either way

        # Classify entries
        work_talaos = []
        personal_talaos = []
        work_journal = []
        personal_journal = []

        for entry in talaos_entries:
            category = classify_entry(entry, is_journal=False)
            if category == 'work':
                work_talaos.append(entry)
            elif category == 'personal':
                personal_talaos.append(entry)
            else:  # neutral - distribute based on context_type
                if context_type == 'work':
                    work_talaos.append(entry)
                elif context_type == 'personal':
                    personal_talaos.append(entry)
                else:  # balanced - split evenly
                    if len(work_talaos) <= len(personal_talaos):
                        work_talaos.append(entry)
                    else:
                        personal_talaos.append(entry)

        for entry in journal_entries:
            category = classify_entry(entry, is_journal=True)
            if category == 'work':
                work_journal.append(entry)
            elif category == 'personal':
                personal_journal.append(entry)
            else:  # neutral
                if context_type == 'work':
                    work_journal.append(entry)
                elif context_type == 'personal':
                    personal_journal.append(entry)
                else:  # balanced
                    if len(work_journal) <= len(personal_journal):
                        work_journal.append(entry)
                    else:
                        personal_journal.append(entry)

        work_context = {'talaos': work_talaos, 'journal': work_journal}
        personal_context = {'talaos': personal_talaos, 'journal': personal_journal}

        return work_context, personal_context

    def _format_context_for_llm(
        self,
        work_context: Dict[str, List],
        personal_context: Dict[str, List]
    ) -> str:
        """
        Format context data for LLM consumption.

        Args:
            work_context: Work-related entries
            personal_context: Personal-related entries

        Returns:
            Formatted context string
        """
        sections = []

        # Work context
        work_sections = []
        if work_context['talaos']:
            work_sections.append("## Work Goals & Tasks")
            for entry in work_context['talaos']:
                work_sections.append(self._format_talaos_entry(entry))

        if work_context['journal']:
            work_sections.append("## Work Reflections")
            for entry in work_context['journal']:
                work_sections.append(self._format_journal_entry(entry))

        if work_sections:
            sections.extend(work_sections)

        # Personal context
        personal_sections = []
        if personal_context['talaos']:
            personal_sections.append("## Personal Goals & Tasks")
            for entry in personal_context['talaos']:
                personal_sections.append(self._format_talaos_entry(entry))

        if personal_context['journal']:
            personal_sections.append("## Personal Reflections")
            for entry in personal_context['journal']:
                personal_sections.append(self._format_journal_entry(entry))

        if personal_sections:
            sections.extend(personal_sections)

        return '\n\n'.join(sections)

    def _format_talaos_entry(self, entry: Dict[str, Any]) -> str:
        """Format a Telos entry for LLM context."""
        entry_type = entry.get('type', 'entry')
        content = entry.get('content', '')
        status = entry.get('status', 'unknown')
        tags = entry.get('tags', [])
        timestamp = entry.get('timestamp', '')[:10]  # YYYY-MM-DD

        tag_str = f" (tags: {', '.join(tags)})" if tags else ""

        return f"**{entry_type.title()}** [{status}] - {timestamp}{tag_str}\n{content}"

    def _format_journal_entry(self, entry: Dict[str, Any]) -> str:
        """Format a journal entry for LLM context."""
        frontmatter = entry.get('frontmatter', {})
        content = entry.get('content', '')
        entry_type = frontmatter.get('type', 'reflection')
        tags = frontmatter.get('tags', [])
        timestamp = frontmatter.get('timestamp', '')[:10]

        tag_str = f" (tags: {', '.join(tags)})" if tags else ""

        # Truncate content if too long
        if len(content) > 500:
            content = content[:500] + "..."

        return f"**{entry_type.title()}** - {timestamp}{tag_str}\n{content}"

    def _enforce_size_limits(self, context: str) -> str:
        """
        Ensure context stays within size limits.

        Args:
            context: Formatted context string

        Returns:
            Truncated context if necessary
        """
        if len(context) <= self.max_context_size:
            return context

        # Truncate to fit within limits
        truncated = context[:self.max_context_size - 100]  # Leave room for truncation message
        truncated += "\n\n[Context truncated due to size limits]"

        logger.warning(f"Context truncated from {len(context)} to {len(truncated)} characters")
        return truncated

    def analyze_goal_progress_from_journal(self, goal_content: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Analyze journal entries for progress on a specific goal.

        Args:
            goal_content: The goal content to search for
            days_back: How many days back to search

        Returns:
            Dictionary with analysis results
        """
        from datetime import datetime, timedelta

        # Get journal entries within time range
        cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()
        journal_entries = self.journal.search_entries(date_from=cutoff_date[:10])

        # Search for goal-related content
        goal_mentions = []
        progress_indicators = []
        completion_signals = []

        goal_lower = goal_content.lower()

        for entry in journal_entries:
            content = entry.get('content', '').lower()
            frontmatter = entry.get('frontmatter', {})

            # Check if goal is mentioned
            if any(word in content for word in goal_lower.split() if len(word) > 3):
                goal_mentions.append(entry)

                # Look for progress indicators
                progress_keywords = ['progress', 'worked on', 'started', 'began', 'continued', 'advanced', 'improved', 'developed']
                if any(keyword in content for keyword in progress_keywords):
                    progress_indicators.append(entry)

                # Look for completion signals
                completion_keywords = ['completed', 'finished', 'done', 'achieved', 'accomplished', 'succeeded', 'finished']
                if any(keyword in content for keyword in completion_keywords):
                    completion_signals.append(entry)

        # Analyze results
        analysis = {
            'goal_content': goal_content,
            'time_period_days': days_back,
            'total_mentions': len(goal_mentions),
            'progress_indicators': len(progress_indicators),
            'completion_signals': len(completion_signals),
            'recent_activity': len([m for m in goal_mentions if self._is_recent_entry(m)]),
            'insights': self._generate_goal_insights(len(goal_mentions), len(progress_indicators), len(completion_signals)),
            'recommended_action': self._recommend_goal_action(len(completion_signals), len(progress_indicators), len(goal_mentions))
        }

        return analysis

    def _is_recent_entry(self, entry: Dict[str, Any]) -> bool:
        """Check if a journal entry is from the last week."""
        from datetime import datetime, timedelta

        try:
            entry_date = datetime.fromisoformat(entry['frontmatter']['timestamp'][:19])
            week_ago = datetime.now() - timedelta(days=7)
            return entry_date > week_ago
        except (KeyError, ValueError):
            return False

    def _generate_goal_insights(self, mentions: int, progress: int, completions: int) -> List[str]:
        """Generate insights based on journal analysis."""
        insights = []

        if completions > 0:
            insights.append(f"🎯 Found {completions} completion signal(s) - goal may be finished!")
        elif progress > 0:
            insights.append(f"📈 Found {progress} progress indicator(s) - active work ongoing")
        elif mentions > 0:
            insights.append(f"💭 Goal mentioned {mentions} time(s) - staying top of mind")

        if mentions == 0:
            insights.append("🤔 No recent journal mentions - consider if this goal is still relevant")
        elif mentions > 5:
            insights.append("🔥 Frequently mentioned - this seems to be a high-priority goal")

        return insights

    def _recommend_goal_action(self, completions: int, progress: int, mentions: int) -> str:
        """Recommend an action based on journal analysis."""
        if completions > 0:
            return "Consider marking this goal as completed"
        elif progress > 2:
            return "Goal appears active - keep up the good work!"
        elif progress > 0:
            return "Some progress detected - consider what next steps to take"
        elif mentions > 0:
            return "Goal is being thought about - time to take action?"
        else:
            return "No recent activity - review if this goal should be updated or removed"