"""
Command-line interface for the personal assistant.

Provides both command-based and interactive conversational modes.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Dict, Any

from config import config
from utils import setup_logging, get_logger
from context import ContextBuilder
from ollama import OllamaClient
from proposals import ProposalEngine
from changes import MutationEngine
from memory import TelosManager, JournalManager


logger = get_logger(__name__)


# ANSI color codes for colored output
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    GRAY = '\033[90m'

    @staticmethod
    def success(text: str) -> str:
        return f"{Colors.GREEN}{text}{Colors.RESET}"

    @staticmethod
    def error(text: str) -> str:
        return f"{Colors.RED}{text}{Colors.RESET}"

    @staticmethod
    def warning(text: str) -> str:
        return f"{Colors.YELLOW}{text}{Colors.RESET}"

    @staticmethod
    def info(text: str) -> str:
        return f"{Colors.BLUE}{text}{Colors.RESET}"

    @staticmethod
    def bold(text: str) -> str:
        return f"{Colors.BOLD}{text}{Colors.RESET}"

    @staticmethod
    def dim(text: str) -> str:
        return f"{Colors.GRAY}{text}{Colors.RESET}"

    @staticmethod
    def cyan(text: str) -> str:
        return f"{Colors.CYAN}{text}{Colors.RESET}"

    @staticmethod
    def green(text: str) -> str:
        return f"{Colors.GREEN}{text}{Colors.RESET}"

    @staticmethod
    def red(text: str) -> str:
        return f"{Colors.RED}{text}{Colors.RESET}"

    @staticmethod
    def yellow(text: str) -> str:
        return f"{Colors.YELLOW}{text}{Colors.RESET}"

    @staticmethod
    def blue(text: str) -> str:
        return f"{Colors.BLUE}{text}{Colors.RESET}"

    @staticmethod
    def gray(text: str) -> str:
        return f"{Colors.GRAY}{text}{Colors.RESET}"


class ProgressBar:
    """Simple progress bar implementation."""

    def __init__(self, total: int, prefix: str = '', suffix: str = '', length: int = 30):
        self.total = total
        self.prefix = prefix
        self.suffix = suffix
        self.length = length
        self.current = 0
        self.start_time = time.time()

    def update(self, current: Optional[int] = None) -> None:
        if current is not None:
            self.current = current

        percent = self.current / self.total if self.total > 0 else 1.0
        filled_length = int(self.length * percent)

        bar = '█' * filled_length + '░' * (self.length - filled_length)

        elapsed = time.time() - self.start_time
        eta = (elapsed / self.current * (self.total - self.current)) if self.current > 0 else 0

        sys.stdout.write(f'\r{self.prefix} [{bar}] {percent:.1%} ({self.current}/{self.total}) ETA: {eta:.1f}s {self.suffix}')
        sys.stdout.flush()

        if self.current >= self.total:
            print()  # New line when complete

    def increment(self, amount: int = 1) -> None:
        self.current += amount
        self.update()


class AutoComplete:
    """Simple command auto-completion helper."""

    @staticmethod
    def suggest_command(partial: str, commands: List[str]) -> List[str]:
        """Return commands that start with the partial input."""
        partial_lower = partial.lower()
        return [cmd for cmd in commands if cmd.lower().startswith(partial_lower)]

    @staticmethod
    def show_suggestions(partial: str, available: List[str], max_suggestions: int = 5) -> None:
        """Show auto-complete suggestions."""
        suggestions = AutoComplete.suggest_command(partial, available)
        if suggestions:
            print(f"\n{Colors.dim('Suggestions:')}")
            for i, suggestion in enumerate(suggestions[:max_suggestions], 1):
                # Highlight the matching part
                match_len = len(partial)
                highlighted = f"{Colors.bold(suggestion[:match_len])}{suggestion[match_len:]}"
                print(f"  {Colors.cyan(str(i))}. {highlighted}")

            if len(suggestions) > max_suggestions:
                print(f"  {Colors.dim('... and')} {len(suggestions) - max_suggestions} {Colors.dim('more')}")
            print(f"{Colors.dim('Press Tab to cycle through suggestions')}\n")


class InteractivePrompt:
    """Enhanced interactive prompts with validation."""

    @staticmethod
    def confirm(message: str, default: bool = False) -> bool:
        """Get yes/no confirmation with colored output."""
        default_text = "(Y/n)" if default else "(y/N)"
        while True:
            response = input(f"{Colors.BOLD}{message}{Colors.RESET} {Colors.dim(default_text)}: ").strip().lower()
            if not response:
                return default
            if response in ['y', 'yes']:
                return True
            if response in ['n', 'no']:
                return False
            print(f"{Colors.error('Please enter y/yes or n/no')}")

    @staticmethod
    def select(options: List[str], prompt: str = "Select an option") -> int:
        """Present numbered options and get selection."""
        print(f"\n{Colors.bold(prompt)}:")
        for i, option in enumerate(options, 1):
            print(f"  {Colors.cyan(str(i))}. {option}")

        while True:
            try:
                choice = input(f"\n{Colors.dim('Enter choice (1-{len(options)}) or q to quit')}: ").strip()
                if choice.lower() in ['q', 'quit']:
                    raise KeyboardInterrupt
                choice_num = int(choice)
                if 1 <= choice_num <= len(options):
                    return choice_num - 1
                print(f"{Colors.error(f'Please enter a number between 1 and {len(options)}')}")
            except ValueError:
                print(f"{Colors.error('Please enter a valid number')}")

    @staticmethod
    def input_with_validation(prompt: str, validator=None, error_msg: str = "Invalid input") -> str:
        """Get input with validation function."""
        while True:
            response = input(f"{Colors.BOLD}{prompt}{Colors.RESET}: ").strip()
            if validator is None or validator(response):
                return response
            print(f"{Colors.error(error_msg)}")


class CLIError(Exception):
    """CLI-specific errors."""
    pass


def setup_argparse() -> argparse.ArgumentParser:
    """Set up the argument parser."""
    parser = argparse.ArgumentParser(
        description="Personal Assistant & Life Coach",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status                    # Show current status
  %(prog)s chat "Help me plan my day"  # Start conversational mode
  %(prog)s goal add "Complete project"  # Add a new goal
  %(prog)s goal list                 # List all goals
  %(prog)s journal add "Great progress today"  # Add journal entry
  %(prog)s query "project planning"   # Search and get AI suggestions
        """
    )

    parser.add_argument(
        '--version',
        action='version',
        version='Personal Assistant v0.1.0'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Set logging level (default: INFO)'
    )

    parser.add_argument(
        '--log-file',
        help='Log to file instead of console'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Help command
    help_parser = subparsers.add_parser('help', help='Show detailed help and usage examples')
    help_parser.add_argument('topic', nargs='?', choices=['setup', 'usage', 'examples', 'troubleshooting'], help='Help topic to show')

    # Status command
    subparsers.add_parser('status', help='Show current status and configuration')

    # Model command
    model_parser = subparsers.add_parser('model', help='AI model management')
    model_subparsers = model_parser.add_subparsers(dest='model_action', help='Model actions')

    # model list
    model_subparsers.add_parser('list', help='List available models from Ollama server')

    # model select
    select_parser = model_subparsers.add_parser('select', help='Select and set a model from available options')
    select_parser.add_argument('--persist', action='store_true', help='Show instructions for persisting the selection')

    # Init command
    subparsers.add_parser('init', help='Initialize memory directory')

    # Chat command
    chat_parser = subparsers.add_parser('chat', help='Start conversational mode')
    chat_parser.add_argument('message', nargs='?', help='Initial message to send')

    # Query command
    query_parser = subparsers.add_parser('query', help='Query assistant for suggestions')
    query_parser.add_argument('message', help='Query message')
    query_parser.add_argument(
        '--context-type',
        choices=['work', 'personal', 'balanced'],
        default='balanced',
        help='Type of context to consider'
    )

    # Goal command
    goal_parser = subparsers.add_parser('goal', help='Goal management')
    goal_subparsers = goal_parser.add_subparsers(dest='goal_action', help='Goal actions')

    # goal add
    add_parser = goal_subparsers.add_parser('add', help='Add a new goal')
    add_parser.add_argument('description', help='Goal description')
    add_parser.add_argument('--tags', nargs='*', help='Tags for the goal')
    add_parser.add_argument('--priority', choices=['low', 'medium', 'high'], default='medium')

    # goal model
    model_parser = goal_subparsers.add_parser('model', help='Change the AI model')
    model_parser.add_argument('model_name', help='Name of the model to use (e.g., llama2, codellama)')
    model_parser.add_argument('--timeout', type=int, help='Timeout in seconds for model requests')

    # goal list
    goal_subparsers.add_parser('list', help='List all goals')

    # goal update
    update_parser = goal_subparsers.add_parser('update', help='Update goal status')
    update_parser.add_argument('goal_id', help='Goal ID to update')
    update_parser.add_argument('status', choices=['active', 'completed', 'cancelled'])

    # Task command
    task_parser = subparsers.add_parser('task', help='Task management')
    task_subparsers = task_parser.add_subparsers(dest='task_action', help='Task actions')

    # task add
    task_add_parser = task_subparsers.add_parser('add', help='Add a new task')
    task_add_parser.add_argument('description', help='Task description')
    task_add_parser.add_argument('--goal', help='Parent goal ID')
    task_add_parser.add_argument('--tags', nargs='*', help='Tags for the task')
    task_add_parser.add_argument('--priority', choices=['low', 'medium', 'high'], default='medium')

    # task list
    task_subparsers.add_parser('list', help='List all tasks')

    # task update
    task_update_parser = task_subparsers.add_parser('update', help='Update task status')
    task_update_parser.add_argument('task_id', help='Task ID to update')
    task_update_parser.add_argument('status', choices=['pending', 'in_progress', 'completed', 'cancelled'])

    # Journal command
    journal_parser = subparsers.add_parser('journal', help='Journal management')
    journal_subparsers = journal_parser.add_subparsers(dest='journal_action', help='Journal actions')

    # journal add
    journal_add_parser = journal_subparsers.add_parser('add', help='Add a journal entry')
    journal_add_parser.add_argument('content', help='Journal entry content')
    journal_add_parser.add_argument('--type', choices=['reflection', 'gratitude', 'learning', 'goal_review', 'planning'], default='reflection')
    journal_add_parser.add_argument('--tags', nargs='*', help='Tags for the entry')
    journal_add_parser.add_argument('--mood', help='Mood indicator')
    journal_add_parser.add_argument('--location', help='Location')

    # Email command
    email_parser = subparsers.add_parser('email', help='Email processing and analysis')
    email_subparsers = email_parser.add_subparsers(dest='email_action', help='Email actions')

    # Config command
    config_parser = subparsers.add_parser('config', help='Configuration management')
    config_subparsers = config_parser.add_subparsers(dest='config_action', help='Config actions')

    # config init
    config_subparsers.add_parser('init', help='Generate .env file with current environment variables')

    # email process
    process_parser = email_subparsers.add_parser('process', help='Process recent emails and generate insights')
    process_parser.add_argument('--server', help='IMAP server address (uses EMAIL_SERVER if not specified)')
    process_parser.add_argument('--port', type=int, help='IMAP server port (uses EMAIL_PORT, default: 993)')
    process_parser.add_argument('--username', help='Email username (uses EMAIL_USERNAME if not specified)')
    process_parser.add_argument('--password', help='Email password (uses EMAIL_PASSWORD if not specified)')
    process_parser.add_argument('--no-ssl', action='store_true', help='Disable SSL (not recommended, uses EMAIL_SSL)')
    process_parser.add_argument('--days', type=int, help='Days back to process (uses EMAIL_DAYS_BACK, default: 7)')

    # journal list
    journal_subparsers.add_parser('list', help='List recent journal entries')
    journal_subparsers.add_parser('search', help='Search journal entries')

    return parser


class InteractiveAssistant:
    """Interactive conversational assistant."""

    def __init__(self, dry_run: bool = False):
        """Initialize the interactive assistant."""
        self.dry_run = dry_run
        self.context_builder = ContextBuilder()
        self.ollama_client = OllamaClient()
        self.proposal_engine = ProposalEngine()
        self.mutation_engine = MutationEngine()

        print(f"{Colors.bold('🤖 Personal Assistant - Interactive Mode')}")
        print(f"{Colors.dim('Available commands: status, chat, query, goal, task, journal, email, model, config, help')}")
        print(f"{Colors.dim('Type')} {Colors.bold('help')} {Colors.dim('for details,')} {Colors.bold('quit')} {Colors.dim('to exit')}")
        print("-" * 70)

    def run(self, initial_message: Optional[str] = None):
        """Run the interactive session."""
        if initial_message:
            self._handle_message(initial_message)

        while True:
            try:
                # Enhanced prompt with command hints
                prompt = f"\n{Colors.bold('You:')} "
                message = input(prompt).strip()
                if not message:
                    continue

                if message.lower() in ['quit', 'exit', 'q']:
                    print(f"{Colors.success('Goodbye! 👋')}")
                    break
                elif message.lower() == 'help':
                    self._show_help()
                else:
                    # Check if this looks like a command (starts with known command)
                    available_commands = ['status', 'chat', 'query', 'goal', 'task', 'journal', 'email', 'model', 'config', 'help']
                    first_word = message.split()[0].lower()

                    if first_word in available_commands:
                        # This looks like a command, suggest using CLI instead
                        print(f"{Colors.warning('💡 Tip:')} Use the main CLI for commands: {Colors.bold(f'python assistant.py {message}')}")
                        print(f"{Colors.dim('Or continue with natural conversation...')}")
                        continue

                    # Check for partial command matches
                    suggestions = AutoComplete.suggest_command(first_word, available_commands)
                    if suggestions and len(first_word) >= 2:
                        AutoComplete.show_suggestions(first_word, available_commands)

                    self._handle_message(message)

            except KeyboardInterrupt:
                print("\nGoodbye! 👋")
                break
            except EOFError:
                print("\nGoodbye! 👋")
                break

    def _show_help(self):
        """Show help information."""
        print(f"\n{Colors.bold('🤖 Interactive Mode Commands')}")
        print("=" * 40)

        commands = [
            ("help", "Show this help information"),
            ("quit/exit/q", "Exit the assistant"),
            ("status", "Show system status and memory"),
            ("chat <message>", "Start direct conversation"),
            ("query <question>", "Ask AI for suggestions"),
            ("goal add/list/update", "Manage goals"),
            ("task add/list/update", "Manage tasks"),
            ("journal add/list", "Manage reflections"),
            ("email process", "Process emails with AI"),
            ("model list/select", "Manage AI models"),
            ("config init", "Generate settings file"),
        ]

        for cmd, desc in commands:
            print(f"  {Colors.cyan(cmd.ljust(18))} {Colors.dim(desc)}")

        print(f"\n{Colors.bold('💬 Regular Conversation')}")
        print(f"{Colors.dim('Just type any message and the assistant will respond with AI-powered suggestions')}")
        print(f"\n{Colors.bold('📝 Examples:')}")
        examples = [
            '"Help me plan my day"',
            '"I need to work on my health goals"',
            '"What\'s my progress on work tasks?"',
            '"Add a reflection about today"',
        ]
        for example in examples:
            print(f"  {Colors.dim('•')} {example}")

    def _handle_message(self, message: str):
        """Handle a user message."""
        print(f"\n🤔 Processing: '{message}'")

        try:
            # Build context
            context = self.context_builder.build_context(message)
            print(f"📚 Found {context['total_entries']} relevant memory entries")

            # Generate mock LLM response (in real implementation, this would call Ollama)
            llm_response = self._generate_mock_response(message, context)

            # Check if this is an analysis response (no JSON proposals)
            if '```json' in llm_response:
                # Extract the text part before JSON for display
                json_start = llm_response.find('```json')
                if json_start > 0:
                    analysis_text = llm_response[:json_start].strip()
                    print("\n" + analysis_text)

                # Parse into proposal
                proposal = self.proposal_engine.parse_llm_output(llm_response, message)

                # Only show proposal details if there are actual proposals
                if proposal.talaos_proposals or proposal.journal_proposals:
                    print(f"📝 Generated proposal with {len(proposal.talaos_proposals)} goal/task + {len(proposal.journal_proposals)} journal changes")

                    # Present proposal
                    presentation = self.proposal_engine.present_proposal(proposal)
                    print("\n" + presentation)

                    # Get user approval
                    if self.dry_run:
                        print("🔍 DRY RUN: Would ask for approval")
                        return

                    approval = input().strip().lower()
                    if approval in ['y', 'yes']:
                        # Apply changes
                        print("🔄 Applying changes...")
                        results = self.mutation_engine.apply_changes_with_audit(proposal, user_approval=True)
                        print(f"✅ Applied {len(results['changes_applied'])} changes successfully")
                    else:
                        print("❌ Changes cancelled by user")
                else:
                    # Analysis complete - no proposals
                    print("ℹ️  Analysis complete - no changes proposed")
            else:
                # Direct response (analysis, information, etc.)
                print("\n" + llm_response)

        except Exception as e:
            print(f"❌ Error: {e}")
            logger.error(f"Error handling message '{message}': {e}", exc_info=True)

    def _generate_mock_response(self, message: str, context: dict) -> str:
        """Generate a mock LLM response for testing (replace with real Ollama call).

        In production, this would send the user's message + existing goals to the LLM
        and ask it to decide whether to update existing goals or create new ones.
        """
        # Simulate what a real LLM would do: analyze the message in context of existing goals
        existing_goals = self._get_existing_goals_summary()

        # Create a prompt that the real LLM would receive
        simulated_prompt = f"""
You are a personal assistant helping someone manage their goals and tasks.

User's existing goals:
{existing_goals}

User's message: "{message}"

Analyze the user's message in the context of their existing goals.
- If they're talking about working on or updating an existing goal, suggest status updates
- If they're asking for new goals or help, suggest creating new goals/tasks
- If they're just sharing information, suggest appropriate reflections

Respond with a JSON proposal for changes to their goal/task management system.
"""

        # For now, simulate LLM decision making with simple heuristics
        # In production, this would be: response = ollama.generate(simulated_prompt)

        msg_lower = message.lower()

        # Check if this is a listing/query request vs a help request
        query_keywords = ['what are', 'show me', 'list', 'tell me about', 'what do i have', 'how do', 'what\'s', 'can you show', 'how are']
        help_keywords = ['help me', 'i need', 'how can i', 'suggest', 'plan', 'organize', 'assist me', 'guide me']
        work_indicators = ['working on', 'in progress', 'started', 'began', 'functional', 'work in progress', 'update', 'status of']

        is_query = any(keyword in msg_lower for keyword in query_keywords)
        is_help = any(keyword in msg_lower for keyword in help_keywords)
        is_work_update = any(indicator in msg_lower for indicator in work_indicators)

        if is_work_update:
            goal_updates = self._detect_goal_updates(message, context)
            if goal_updates:
                return self._generate_goal_update_response(goal_updates)

        # Handle query requests first (they take precedence)
        if is_query:
            # Check if this is an evaluative query (asking for analysis/feedback)
            evaluative_keywords = ['how do', 'how are', 'what do you think', 'analyze', 'review', 'evaluate']
            is_evaluative = any(keyword in msg_lower for keyword in evaluative_keywords)

            if is_evaluative and ('goal' in msg_lower or 'progress' in msg_lower):
                # Provide goal analysis instead of just listing
                return self._generate_goal_analysis_response()
            if 'goal' in msg_lower:
                goals_list = self._format_goals_list()
                return f"""I see you're asking about your goals. Based on your current goals, here's what you have:

Current Goals:
{goals_list}

If you'd like help with any of these goals or want to add new ones, let me know!

{{
  "proposal_id": "mock_goals_query",
  "reasoning": "User is asking to see their current goals",
  "confidence": 0.9,
  "talaos_proposals": [],
  "journal_proposals": []
}}
"""
            elif 'task' in msg_lower:
                tasks_list = self._format_tasks_list()
                return f"""You're asking about your tasks. Here's your current task status:

Current Tasks:
{tasks_list}

Let me know if you need help with any of these tasks!

{{
  "proposal_id": "mock_tasks_query",
  "reasoning": "User is asking to see their current tasks",
  "confidence": 0.9,
  "talaos_proposals": [],
  "journal_proposals": []
}}
"""

        # Handle goal-related queries
        if 'goal' in msg_lower:
            if is_query:
                # User is asking to see goals, not add them
                goals_list = self._format_goals_list()
                return f"""I see you're asking about your goals. Based on your current goals, here's what you have:

Current Goals:
{goals_list}

If you'd like help with any of these goals or want to add new ones, let me know!

{{
  "proposal_id": "mock_goals_query",
  "reasoning": "User is asking to see their current goals",
  "confidence": 0.9,
  "talaos_proposals": [],
  "journal_proposals": []
}}
"""
            else:
                # User wants help with goals
                return 'I understand you want help with goals. Let me suggest some structure.\n\n{\n  "proposal_id": "mock_goals_help",\n  "reasoning": "User wants help with goal management",\n  "confidence": 0.8,\n  "talaos_proposals": [\n    {\n      "action": "add_goal",\n      "content": "Set up personal goal tracking system",\n      "tags": ["planning", "goals"],\n      "priority": "medium"\n    }\n  ],\n  "journal_proposals": [\n    {\n      "action": "add_entry",\n      "content": "Started thinking about my goals and how to track them effectively.",\n      "entry_type": "reflection",\n      "tags": ["goals", "planning"]\n    }\n  ]\n}'

        # Handle task-related queries
        if 'task' in msg_lower:
            if is_query:
                tasks_list = self._format_tasks_list()
                return f"""You're asking about your tasks. Here's your current task status:

Current Tasks:
{tasks_list}

Let me know if you need help with any of these tasks!

{{
  "proposal_id": "mock_tasks_query",
  "reasoning": "User is asking to see their current tasks",
  "confidence": 0.9,
  "talaos_proposals": [],
  "journal_proposals": []
}}
"""
            else:
                return """
I can help you with task management. Let me suggest organizing your tasks.

{
  "proposal_id": "mock_tasks_help",
  "reasoning": "User wants help with task management",
  "confidence": 0.8,
  "talaos_proposals": [
    {
      "action": "add_task",
      "content": "Review and organize current task list",
      "tags": ["organization", "tasks"],
      "priority": "medium"
    }
  ],
  "journal_proposals": []
}
"""

        # Handle project/work related requests
        if 'project' in msg_lower or 'work' in msg_lower:
            return 'I understand you want help with project planning. Based on your memory, I suggest:\n\n{\n  "proposal_id": "mock_project_help",\n  "reasoning": "You mentioned project planning, so I\'ll help organize your work",\n  "confidence": 0.8,\n  "talaos_proposals": [\n    {\n      "action": "add_task",\n      "content": "Complete project requirements analysis",\n      "tags": ["work", "planning"],\n      "priority": "high"\n    }\n  ],\n  "journal_proposals": [\n    {\n      "action": "add_entry",\n      "content": "Focused on project planning today and made progress on understanding the requirements.",\n      "entry_type": "reflection",\n      "tags": ["work", "progress", "planning"]\n    }\n  ]\n}'

        # Default response for other help requests
        if is_help:
            return 'I understand you have a question. Let me help organize your thoughts.\n\n{\n  "proposal_id": "mock_general_help",\n  "reasoning": "General assistance requested",\n  "confidence": 0.6,\n  "talaos_proposals": [\n    {\n      "action": "add_goal",\n      "content": "Clarify goals and create action plan",\n      "tags": ["planning"],\n      "priority": "medium"\n    }\n  ],\n  "journal_proposals": []\n}'

        # For unrecognized queries, provide information without proposals
        goals_count = len([e for e in context.get('entries', []) if e.get('type') == 'goal'])
        tasks_count = len([e for e in context.get('entries', []) if e.get('type') == 'task'])
        journal_count = len([e for e in context.get('entries', []) if 'reflection' in str(e)])

        return f"""I see you're asking something, but I'm not sure exactly what you need help with.

Based on your current memory, you have:
- {goals_count} goals
- {tasks_count} tasks
- {journal_count} journal entries

Could you clarify what you'd like help with?

{{
  "proposal_id": "mock_unclear_query",
  "reasoning": "Query is unclear, providing status information instead",
  "confidence": 0.5,
  "talaos_proposals": [],
  "journal_proposals": []
}}
"""

    def _detect_goal_updates(self, message: str, context: dict) -> List[Dict[str, Any]]:
        """Detect if the user is talking about working on existing goals."""
        try:
            from memory import TelosManager
            talaos = TelosManager()
            goals = talaos.get_goals()

            msg_lower = message.lower()
            updates = []

            for goal in goals:
                goal_content = goal.get('content', '').lower()
                goal_id = goal.get('id', '')

                # Check if the message mentions working on this goal
                # Look for significant words (4+ characters) that appear in both
                goal_words = set(word for word in goal_content.split() if len(word) >= 4)
                message_words = set(word for word in msg_lower.split() if len(word) >= 4)

                if goal_words.intersection(message_words):
                    # Found a potential match - user is mentioning this goal as work in progress
                    # Since goals can be "active" while working on them, suggest keeping it active
                    # This provides confirmation and acknowledgment
                    updates.append({
                        'goal_id': goal_id,
                        'goal_content': goal.get('content', ''),
                        'current_status': goal.get('status', 'unknown'),
                        'suggested_status': 'active'  # Keep it active as confirmation
                    })

            return updates[:2]  # Limit to 2 updates max

        except Exception as e:
            # If goal detection fails, return empty list
            return []

    def _generate_goal_update_response(self, goal_updates: List[Dict[str, Any]]) -> str:
        """Generate response for goal status updates."""
        if not goal_updates:
            return self._generate_default_help_response()

        talaos_proposals = []
        for update in goal_updates:
            talaos_proposals.append({
                "action": "update_status",
                "goal_id": update['goal_id'],
                "new_status": update['suggested_status']
            })

        response = "I understand you're working on your goals! Based on what you said, I suggest updating the status of these goals to 'active' (to show they're being worked on):\n\n"

        for update in goal_updates:
            response += f"- **{update['goal_content']}** (currently: {update['current_status']})\n"

        response += "\nThis will help track your progress on these active projects.\n\n"

        # Add JSON proposal
        import json
        json_data = {
            "proposal_id": "mock_goal_status_update",
            "reasoning": "User mentioned working on existing goals, suggesting status updates",
            "confidence": 0.8,
            "talaos_proposals": talaos_proposals,
            "journal_proposals": []
        }
        json_part = json.dumps(json_data, indent=2)

        return response + "```json\n" + json_part + "\n```"

    def _get_existing_goals_summary(self) -> str:
        """Get a summary of existing goals for LLM context."""
        try:
            from memory import TelosManager
            talaos = TelosManager()
            goals = talaos.get_goals()

            if not goals:
                return "No existing goals."

            summary_lines = []
            for goal in goals[:5]:  # Limit to 5 most recent
                content = goal.get('content', 'Unknown goal')
                status = goal.get('status', 'unknown')
                goal_id = goal.get('id', 'unknown')
                summary_lines.append(f"- {goal_id}: {content} (status: {status})")

            return "\n".join(summary_lines)

        except Exception as e:
            return f"Error retrieving goals: {e}"

    def _generate_goal_analysis_response(self) -> str:
        """Generate an analysis of current goals and progress, including journal insights."""
        try:
            from memory import TelosManager
            from context import ContextBuilder

            telos = TelosManager()
            context_builder = ContextBuilder()
            goals = telos.get_goals()

            if not goals:
                return 'You don\'t have any goals set yet. Would you like me to help you create some?\n\n{\n  "proposal_id": "mock_goal_analysis_empty",\n  "reasoning": "User asked for goal analysis but has no goals",\n  "confidence": 0.9,\n  "talaos_proposals": [],\n  "journal_proposals": []\n}'

            # Analyze goals
            total_goals = len(goals)
            active_goals = len([g for g in goals if g.get('status') == 'active'])
            completed_goals = len([g for g in goals if g.get('status') == 'completed'])

            # Get recent goals (last 3)
            recent_goals = sorted(goals, key=lambda x: x.get('timestamp', ''), reverse=True)[:3]

            analysis = f"Here's an analysis of your {total_goals} goals:\n\n"
            analysis += f"📊 **Progress Overview:**\n"
            analysis += f"• {active_goals} active goals\n"
            analysis += f"• {completed_goals} completed goals\n"
            analysis += f"• {total_goals - active_goals - completed_goals} other status\n\n"

            analysis += "🎯 **Your Recent Goals:**\n"
            for goal in recent_goals:
                status = goal.get('status', 'unknown')
                content = goal.get('content', 'No content')[:60]
                analysis += f"• [{status}] {content}\n"

            # Analyze journal entries for goal progress
            journal_insights = []
            for goal in recent_goals[:2]:  # Analyze top 2 recent goals
                goal_content = goal.get('content', '')
                journal_analysis = context_builder.analyze_goal_progress_from_journal(goal_content, days_back=30)

                if journal_analysis['total_mentions'] > 0:
                    journal_insights.append(f"📝 **{goal_content[:40]}...**")
                    journal_insights.extend(f"   {insight}" for insight in journal_analysis['insights'])
                    journal_insights.append(f"   💡 {journal_analysis['recommended_action']}")

            if journal_insights:
                analysis += "\n📖 **Journal Insights:**\n"
                analysis += "\n".join(journal_insights[:6])  # Limit to 6 insights
                analysis += "\n"

            # Provide feedback
            if completed_goals > 0:
                completion_rate = completed_goals / total_goals * 100
                analysis += f"\n✅ **Great progress!** You've completed {completion_rate:.0f}% of your goals.\n"
            else:
                analysis += f"\n💪 **Keep going!** You have {active_goals} active goals to work on.\n"

            if active_goals > 5:
                analysis += "📝 **Suggestion:** Consider focusing on your highest priority goals.\n"

            analysis += "\nWould you like me to help you review or update any of these goals?\n\n"

            return analysis + '\n\n```json\n{\n  "proposal_id": "mock_goal_analysis",\n  "reasoning": "Providing analysis of user\'s current goals and journal insights",\n  "confidence": 0.9,\n  "talaos_proposals": [],\n  "journal_proposals": []\n}\n```'

        except Exception as e:
            return f'I tried to analyze your goals but encountered an error: {e}\n\n{{\n  "proposal_id": "mock_goal_analysis_error",\n  "reasoning": "Error occurred during goal analysis",\n  "confidence": 0.5,\n  "talaos_proposals": [],\n  "journal_proposals": []\n}}'

    def _generate_default_help_response(self) -> str:
        """Generate a default help response when no specific matches found."""
        return 'I understand you might need some help. Would you like me to suggest some goals or help you organize your current tasks?\n\n{\n  "proposal_id": "mock_default_help",\n  "reasoning": "General help request without specific context",\n  "confidence": 0.5,\n  "talaos_proposals": [\n    {\n      "action": "add_goal",\n      "content": "Get organized and clarify objectives",\n      "tags": ["planning"],\n      "priority": "medium"\n    }\n  ],\n  "journal_proposals": []\n}'

    def _format_goals_list(self) -> str:
        """Format current goals for display."""
        try:
            from memory import TelosManager
            talaos = TelosManager()
            goals = talaos.get_goals()

            if not goals:
                return "- No goals found"

            lines = []
            for goal in goals[:5]:  # Show up to 5 goals
                status = goal.get('status', 'unknown')
                content = goal.get('content', 'No content')[:60]
                lines.append(f"- [{status}] {content}")

            if len(goals) > 5:
                lines.append(f"- ... and {len(goals) - 5} more goals")

            return "\n".join(lines)
        except Exception:
            return "- Unable to retrieve goals"

    def _format_tasks_list(self) -> str:
        """Format current tasks for display."""
        try:
            from memory import TelosManager
            talaos = TelosManager()
            tasks = talaos.get_tasks()

            if not tasks:
                return "- No tasks found"

            lines = []
            for task in tasks[:5]:  # Show up to 5 tasks
                status = task.get('status', 'unknown')
                content = task.get('content', 'No content')[:60]
                lines.append(f"- [{status}] {content}")

            if len(tasks) > 5:
                lines.append(f"- ... and {len(tasks) - 5} more tasks")

            return "\n".join(lines)
        except Exception:
            return "- Unable to retrieve tasks"
        else:
            return """
I understand you have a question. Let me help organize your thoughts.

{
  "proposal_id": "mock_general_help",
  "reasoning": "General assistance requested",
  "confidence": 0.6,
  "talaos_proposals": [
    {
      "action": "add_goal",
      "content": "Clarify goals and create action plan",
      "tags": ["planning"],
      "priority": "medium"
    }
  ],
  "journal_proposals": []
}
"""


def handle_status(args: argparse.Namespace) -> None:
    """Handle the status command."""
    print(f"{Colors.bold('🤖 Personal Assistant Status')}")
    print("=" * 50)
    print(f"{Colors.info('📍 Ollama URL:')} {Colors.bold(config.ollama_url)}")
    print(f"{Colors.info('🤖 Current Model:')} {Colors.bold(config.ollama_model)}")
    print(f"{Colors.info('📁 Memory Directory:')} {Colors.bold(config.memory_dir)}")
    print(f"{Colors.info('🔧 Log Level:')} {Colors.bold(config.log_level)}")
    print(f"{Colors.info('📊 Max Context Size:')} {Colors.bold(str(config.max_context_size))} tokens")

    # Check memory systems
    import os
    if os.path.exists(config.memory_dir):
        print(f"✅ Memory directory: EXISTS ({config.memory_dir})")

        # Check file counts
        talaos = TelosManager()
        journal = JournalManager()

        talaos_entries = len(talaos.get_all_entries())
        journal_entries = len(journal.get_all_entries())

        print(f"🎯 Telos entries: {talaos_entries}")
        print(f"📖 Journal entries: {journal_entries}")

        # Check change history
        changes = MutationEngine()
        change_history = changes.get_change_history()
        print(f"📋 Change records: {len(change_history)}")
    else:
        print(f"❌ Memory directory: NOT FOUND ({config.memory_dir})")
        print("   Run 'assistant init' to create it")


def handle_init(args: argparse.Namespace) -> None:
    """Handle the init command."""
    import os
    from pathlib import Path

    memory_dir = config.memory_dir
    telos_file = Path(memory_dir) / "telos.jsonl"
    journal_file = Path(memory_dir) / "journal.md"

    # Check for existing data files
    telos_exists = telos_file.exists() and telos_file.stat().st_size > 0
    journal_exists = journal_file.exists() and journal_file.stat().st_size > 0

    if telos_exists or journal_exists:
        print(f"{Colors.warning('⚠️  Existing memory files detected!')}")
        if telos_exists:
            print(f"{Colors.info('📋 Telos file:')} {telos_file} ({Colors.bold('contains data')})")
        if journal_exists:
            print(f"{Colors.info('📖 Journal file:')} {journal_file} ({Colors.bold('contains data')})")

        print(f"\n{Colors.bold('Important:')} Your personal data (goals, tasks, journal entries) will be preserved.")
        print(f"{Colors.dim('The init command only creates the directory structure if missing.')}")
        print(f"{Colors.dim('No existing data will be modified or overwritten.')}\n")

    if os.path.exists(memory_dir):
        print(f"{Colors.success('✅ Memory directory already exists:')} {memory_dir}")

        # Check if we need to initialize the managers (they create files if missing)
        if not telos_exists or not journal_exists:
            print(f"{Colors.info('🔄 Initializing missing memory files...')}")
            try:
                talaos = TelosManager()  # Creates telos.jsonl if missing
                journal = JournalManager()  # Creates journal.md if missing
                print(f"{Colors.success('✅ Memory files initialized')}")
            except Exception as e:
                print(f"{Colors.error('❌ Failed to initialize memory files:')} {e}")
                return

        print(f"{Colors.success('🎉 Ready to start using the assistant!')}")
        print(f"{Colors.dim('💡 Your data is safe and will never be overwritten by updates.')}")
    else:
        try:
            os.makedirs(memory_dir, exist_ok=True)
            print(f"{Colors.success('✅ Created memory directory:')} {memory_dir}")

            # Initialize empty files
            talaos = TelosManager()
            journal = JournalManager()

            print(f"{Colors.success('✅ Initialized memory files')}")
            print(f"{Colors.success('🎉 Ready to start using the assistant!')}")

        except Exception as e:
            print(f"{Colors.error('❌ Failed to initialize:')} {e}")


def handle_chat(args: argparse.Namespace) -> None:
    """Handle the chat command."""
    assistant = InteractiveAssistant(dry_run=args.dry_run)
    assistant.run(args.message)


def handle_query(args: argparse.Namespace) -> None:
    """Handle the query command."""
    print(f"🤔 Processing query: '{args.message}'")
    print(f"🎯 Context type: {args.context_type}")

    try:
        # Build context
        context_builder = ContextBuilder()
        context = context_builder.build_context(args.message, context_type=args.context_type)

        print(f"📚 Found {context['total_entries']} relevant entries")
        print(f"📏 Context size: {context['context_size_chars']} chars")

        # Generate and parse proposal
        assistant = InteractiveAssistant(dry_run=args.dry_run)
        llm_response = assistant._generate_mock_response(args.message, context)

        # Parse proposal first
        proposal_engine = ProposalEngine()
        proposal = proposal_engine.parse_llm_output(llm_response, args.message)

        # Check if this is an analysis response (has JSON but 0 proposals)
        if '```json' in llm_response and not (proposal.talaos_proposals or proposal.journal_proposals):
            # Extract and display analysis text
            json_start = llm_response.find('```json')
            if json_start > 0:
                analysis_text = llm_response[:json_start].strip()
                print("\n" + analysis_text)
            print("ℹ️  Analysis complete - no changes proposed")
        else:
            # Normal proposal flow
            print(f"📝 Generated proposal with {len(proposal.talaos_proposals)} goal/task + {len(proposal.journal_proposals)} journal changes")

            # Present proposal
            presentation = proposal_engine.present_proposal(proposal)
            print("\n" + presentation)

            if not args.dry_run and (proposal.talaos_proposals or proposal.journal_proposals):
                approval = input().strip().lower()
                if approval in ['y', 'yes']:
                    mutation_engine = MutationEngine()
                    results = mutation_engine.apply_changes_with_audit(proposal, user_approval=True)
                    print(f"✅ Applied {len(results['changes_applied'])} changes")
                else:
                    print("❌ Cancelled")

        if not args.dry_run:
            approval = input().strip().lower()
            if approval in ['y', 'yes']:
                mutation_engine = MutationEngine()
                results = mutation_engine.apply_changes_with_audit(proposal, user_approval=True)
                print(f"✅ Applied {len(results['changes_applied'])} changes")
            else:
                print("❌ Cancelled")

    except Exception as e:
        print(f"❌ Error: {e}")


def handle_goal(args: argparse.Namespace) -> None:
    """Handle goal-related commands."""
    talaos = TelosManager()

    if args.goal_action == 'add':
        try:
            goal_id = talaos.add_goal(
                content=args.description,
                tags=args.tags,
                priority=args.priority
            )
            print(f"✅ Added goal: {goal_id}")
            print(f"   Description: {args.description}")
        except Exception as e:
            print(f"❌ Error adding goal: {e}")

    elif args.goal_action == 'list':
        try:
            goals = talaos.get_goals()
            if goals:
                print(f"{Colors.success('🎯 Found')} {Colors.bold(str(len(goals)))} {Colors.success('goals:')}")
                for goal in goals:
                    status = goal.get('status', 'unknown')
                    content = goal.get('content', 'No content')

                    # Color code status
                    if status == 'active':
                        status_color = Colors.green
                    elif status == 'completed':
                        status_color = Colors.cyan
                    elif status == 'cancelled':
                        status_color = Colors.red
                    else:
                        status_color = Colors.yellow

                    print(f"   {Colors.dim('•')} [{status_color(status)}] {content}")
            else:
                print(f"{Colors.warning('📭 No goals found')}")
        except Exception as e:
            print(f"{Colors.error('❌ Error listing goals:')} {e}")

    elif args.goal_action == 'update':
        try:
            success = talaos.update_status(args.goal_id, args.status)
            if success:
                print(f"✅ Updated goal {args.goal_id} status to: {args.status}")
            else:
                print(f"❌ Goal {args.goal_id} not found")
        except Exception as e:
            print(f"❌ Error updating goal: {e}")

    elif args.goal_action == 'model':
        try:
            # This is a simplified implementation - in production, this would update config
            print(f"🔄 Switching to model: {args.model_name}")
            if args.timeout:
                print(f"   Timeout: {args.timeout} seconds")
                print("⚠️  Note: Timeout changes require restarting the assistant")
            print("✅ Model updated (restart required for changes to take effect)")
            print(f"   Set OLLAMA_MODEL={args.model_name} in your environment")
        except Exception as e:
            print(f"❌ Error updating model: {e}")


def handle_task(args: argparse.Namespace) -> None:
    """Handle task-related commands."""
    talaos = TelosManager()

    if args.task_action == 'add':
        try:
            task_id = talaos.add_task(
                content=args.description,
                parent_goal=args.goal,
                tags=args.tags,
                priority=args.priority
            )
            print(f"✅ Added task: {task_id}")
            print(f"   Description: {args.description}")
            if args.goal:
                print(f"   Parent goal: {args.goal}")
        except Exception as e:
            print(f"❌ Error adding task: {e}")

    elif args.task_action == 'list':
        try:
            tasks = talaos.get_tasks()
            if tasks:
                print(f"{Colors.success('📋 Found')} {Colors.bold(str(len(tasks)))} {Colors.success('tasks:')}")
                for task in tasks:
                    status = task.get('status', 'unknown')
                    content = task.get('content', 'No content')
                    parent = task.get('parent_goal', 'No parent')

                    # Color code status
                    if status == 'in_progress':
                        status_color = Colors.blue
                    elif status == 'completed':
                        status_color = Colors.cyan
                    elif status == 'pending':
                        status_color = Colors.yellow
                    elif status == 'cancelled':
                        status_color = Colors.red
                    else:
                        status_color = Colors.gray

                    print(f"   {Colors.dim('•')} [{status_color(status)}] {content}")
                    if parent and parent != 'No parent':
                        print(f"     {Colors.dim('Parent:')} {Colors.dim(parent)}")
            else:
                print(f"{Colors.warning('📭 No tasks found')}")
        except Exception as e:
            print(f"{Colors.error('❌ Error listing tasks:')} {e}")

    elif args.task_action == 'update':
        try:
            success = talaos.update_status(args.task_id, args.status)
            if success:
                print(f"✅ Updated task {args.task_id} status to: {args.status}")
            else:
                print(f"❌ Task {args.task_id} not found")
        except Exception as e:
            print(f"❌ Error updating task: {e}")


def handle_journal(args: argparse.Namespace) -> None:
    """Handle journal-related commands."""
    journal = JournalManager()

    if args.journal_action == 'add':
        try:
            timestamp = journal.add_entry(
                content=args.content,
                entry_type=args.type,
                tags=args.tags,
                mood=args.mood,
                location=args.location
            )
            print(f"✅ Added journal entry: {timestamp}")
            print(f"   Type: {args.type}")
            print(f"   Content: {args.content[:50]}...")
        except Exception as e:
            print(f"❌ Error adding journal entry: {e}")


def handle_email(args: argparse.Namespace) -> None:
    """Handle email-related commands."""
    if args.email_action == 'process':
        try:
            from email_integration import EmailProcessor

            # Use config defaults if arguments not provided
            server = args.server or config.email_server
            port = args.port if args.port is not None else config.email_port
            username = args.username or config.email_username
            password = args.password or config.email_password
            use_ssl = not args.no_ssl if args.no_ssl else config.email_ssl
            days = args.days if args.days is not None else config.email_days_back

            # Validate required fields
            if not server:
                print("❌ Error: No email server specified. Set EMAIL_SERVER environment variable or use --server")
                return
            if not username:
                print("❌ Error: No email username specified. Set EMAIL_USERNAME environment variable or use --username")
                return
            if not password:
                print("❌ Error: No email password specified. Set EMAIL_PASSWORD environment variable or use --password")
                return

            print(f"{Colors.info('📧 Connecting to')} {Colors.bold(f'{server}:{port}')}...")
            print(f"{Colors.info('👤 User:')} {Colors.bold(username)}")
            print(f"{Colors.info('🔒 SSL:')} {Colors.bold('Enabled' if use_ssl else 'Disabled')}")
            print(f"{Colors.info('📅 Processing emails from last')} {Colors.bold(f'{days} days')}...")

            processor = EmailProcessor()
            results = processor.process_emails(
                server=server,
                port=port,
                username=username,
                password=password,
                use_ssl=use_ssl
            )

            # Report results
            print(f"\n{Colors.bold('📊 Processing Results:')}")
            success_color = Colors.success if results['success'] else Colors.error
            print(f"{success_color('✅ Success:')} {results['success']}")
            print(f"{Colors.info('🔗 Connection:')} {results['connection_status']}")
            emails_found = results.get('emails_found', 0)
            print(f"{Colors.info('📧 Emails Found:')} {emails_found}")
            print(f"{Colors.info('📧 Emails Processed:')} {Colors.bold(str(results['emails_processed']))}")

            if results['errors']:
                print(f"{Colors.warning('⚠️  Errors:')} {len(results['errors'])}")
                for error in results['errors'][:3]:  # Show first 3 errors
                    print(f"   {Colors.dim('•')} {error}")

            if results['news_brief']:
                print(f"\n{Colors.bold('📰 News Brief:')}")
                print(f"{results['news_brief']}")

            if results['suggested_todos']:
                print(f"\n{Colors.bold('📋 Suggested Todos')} ({len(results['suggested_todos'])}):")
                for i, todo in enumerate(results['suggested_todos'], 1):
                    print(f"  {Colors.cyan(str(i))}. {todo.get('content', 'Unknown')}")
                    print(f"     {Colors.dim('Priority:')} {todo.get('priority', 'medium')}")
                    if todo.get('reason'):
                        print(f"     {Colors.dim('Reason:')} {todo.get('reason', '')[:100]}...")

                # Ask if user wants to add these todos
                if results['suggested_todos']:
                    if InteractivePrompt.confirm(f"Add these {len(results['suggested_todos'])} suggested todos to your list?", default=False):
                        added_count = 0
                        for todo in results['suggested_todos']:
                            try:
                                # Add as task (could be enhanced to add as goals too)
                                task_id = processor.telos.add_task(
                                    content=todo.get('content', ''),
                                    tags=['email-suggested'],
                                    priority=todo.get('priority', 'medium')
                                )
                                added_count += 1
                                print(f"{Colors.success('✅ Added todo:')} {todo.get('content', '')[:50]}...")
                            except Exception as e:
                                print(f"{Colors.error('❌ Failed to add todo:')} {e}")

                        print(f"{Colors.success('📋 Successfully added')} {added_count} {Colors.success('todos to your list!')}")
                    else:
                        print(f"{Colors.dim('❌ Todo addition cancelled')}")
            elif results['emails_processed'] == 0 and results['success'] and emails_found > 0:
                print(f"\n{Colors.success('✅ All caught up!')}")
                print(f"{Colors.info('📧 Found')} {emails_found} {Colors.info('recent emails, but all have already been processed.')}")
                print(f"{Colors.dim('💡 New emails will be processed automatically on your next run!')}")
            elif results['emails_processed'] == 0 and emails_found == 0:
                print(f"\n{Colors.info('📭 No emails found in the last 7 days.')}")
                print(f"{Colors.dim('💡 Check your email settings or try again later.')}")


        except Exception as e:
            print(f"❌ Email processing failed: {e}")
            logger.error(f"Email processing error: {e}", exc_info=True)


def handle_model(args: argparse.Namespace) -> None:
    """Handle model-related commands."""
    try:
        from ollama import OllamaClient
        client = OllamaClient()

        if args.model_action == 'list':
            models = client.get_available_models()
            if not models:
                print("❌ No models found on Ollama server")
                return

            print("🤖 Available Ollama Models:")
            print("=" * 50)
            for i, model in enumerate(models, 1):
                name = model.get('name', 'Unknown')
                size_mb = model.get('size', 0) // (1024 * 1024)
                family = model.get('details', {}).get('family', 'Unknown')
                print(f"{i:2d}. {name}")
                print(f"    Size: {size_mb} MB | Family: {family}")

            current_model = config.ollama_model
            print(f"\n🎯 Current model: {current_model}")
            print(f"💡 Use 'assistant model select' to choose a different model")

        elif args.model_action == 'select':
            models = client.get_available_models()
            if not models:
                print("❌ No models found on Ollama server")
                return

            print(f"\n{Colors.bold('🤖 Select an Ollama Model')}")
            print("=" * 40)

            # Create options list for the select function
            options = []
            for model in models:
                name = model.get('name', 'Unknown')
                size_mb = model.get('size', 0) // (1024 * 1024)
                family = model.get('details', {}).get('family', 'Unknown')
                options.append(f"{name} ({size_mb} MB, {family})")

            try:
                selected_index = InteractivePrompt.select(options, "Choose your AI model")
                selected_model = models[selected_index]['name']

                # Set the environment variable
                import os
                os.environ['OLLAMA_MODEL'] = selected_model

                print(f"✅ Selected model: {selected_model}")

                # Test the model quickly
                print("🧪 Testing model...")
                try:
                    test_response = client.generate_text("Hello", model=selected_model, timeout=10)
                    print(f"✅ Model test successful: {str(test_response)[:50]}...")
                except Exception as e:
                    print(f"⚠️  Model test failed: {e}")

                print(f"\n💡 Model selected for current session: {selected_model}")

                if args.persist:
                    # Update .env file with the selected model
                    try:
                        _update_env_file('OLLAMA_MODEL', selected_model)
                        print(f"✅ Model '{selected_model}' saved to .env file for future sessions")
                    except Exception as e:
                        print(f"⚠️  Could not update .env file: {e}")
                        print(f"   To persist manually: export OLLAMA_MODEL={selected_model}")
                else:
                    print(f"   To use in future sessions:")
                    print(f"   - Run: python assistant.py config init")
                    print(f"   - Or manually: export OLLAMA_MODEL={selected_model}")

            except KeyboardInterrupt:
                print("\n❌ Selection cancelled")
                return

    except Exception as e:
        print(f"❌ Error accessing Ollama server: {e}")
        print("💡 Make sure Ollama is running and OLLAMA_URL is set correctly")


def _persist_model_selection(model_name: str) -> None:
    """Display instructions for persisting model selection (no longer auto-persists)."""
    print("💡 To persist this model selection for future sessions:")
    print(f"   Add this line to your ~/.bashrc or ~/.profile:")
    print(f"   export OLLAMA_MODEL={model_name}")
    print("   Then run: source ~/.bashrc")


def handle_config(args: argparse.Namespace) -> None:
    """Handle configuration-related commands."""
    if args.config_action == 'init':
        try:
            _generate_env_file()
            print("✅ Generated .env file with current environment variables")
            print("   Review and edit .env as needed for your configuration")
        except Exception as e:
            print(f"❌ Failed to generate .env file: {e}")


def _update_env_file(key: str, value: str) -> None:
    """Update a specific key-value pair in the .env file."""
    env_file = Path('.env')

    # Read existing content
    content_lines = []
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                content_lines = f.read().splitlines()
        except Exception:
            # If we can't read, start fresh
            content_lines = [
                "# Personal Assistant Environment Configuration",
                "# This file contains environment variables for the personal assistant",
                "# DO NOT commit this file to version control - it may contain sensitive information",
                "",
            ]

    # Update or add the key
    updated = False
    for i, line in enumerate(content_lines):
        if line.startswith(f'{key}='):
            content_lines[i] = f'{key}={value}'
            updated = True
            break

    if not updated:
        # Add to the appropriate section
        ollama_section_found = False
        for i, line in enumerate(content_lines):
            if line == "# Ollama Configuration":
                # Insert after the Ollama section header
                j = i + 1
                while j < len(content_lines) and not content_lines[j].startswith('# ') and content_lines[j].strip():
                    j += 1
                content_lines.insert(j, f'{key}={value}')
                updated = True
                break

        if not updated:
            # Append at the end if no appropriate section found
            content_lines.append(f'{key}={value}')

    # Write back
    with open(env_file, 'w') as f:
        f.write('\n'.join(content_lines))


def _generate_env_file() -> None:
    """Generate .env file with current environment variables."""
    env_file = Path('.env')

    # Define the variables we want to save
    config_vars = [
        ('OLLAMA_URL', 'Ollama server endpoint'),
        ('OLLAMA_MODEL', 'Default AI model'),
        ('OLLAMA_TIMEOUT', 'Request timeout in seconds'),
        ('EMAIL_SERVER', 'IMAP server address'),
        ('EMAIL_PORT', 'IMAP server port'),
        ('EMAIL_USERNAME', 'Email account username'),
        ('EMAIL_PASSWORD', 'Email account password'),
        ('EMAIL_SSL', 'Use SSL connection'),
        ('EMAIL_DAYS_BACK', 'Days of email history to process'),
        ('MEMORY_DIR', 'Memory file storage location'),
        ('MAX_CONTEXT_SIZE', 'Maximum context tokens'),
        ('LOG_LEVEL', 'Logging verbosity'),
        ('LOG_FILE', 'Optional log file path'),
    ]

    # Read existing file if it exists
    existing_vars = {}
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        existing_vars[key.strip()] = value.strip()
        except Exception:
            pass  # If we can't read it, we'll overwrite

    # Generate new content
    content_lines = [
        "# Personal Assistant Environment Configuration",
        "# This file contains environment variables for the personal assistant",
        "# DO NOT commit this file to version control - it may contain sensitive information",
        "",
    ]

    # Group variables by category
    categories = {
        "Ollama Configuration": ['OLLAMA_URL', 'OLLAMA_MODEL', 'OLLAMA_TIMEOUT'],
        "Email Configuration": ['EMAIL_SERVER', 'EMAIL_PORT', 'EMAIL_USERNAME', 'EMAIL_PASSWORD', 'EMAIL_SSL', 'EMAIL_DAYS_BACK'],
        "Memory Configuration": ['MEMORY_DIR', 'MAX_CONTEXT_SIZE'],
        "Logging Configuration": ['LOG_LEVEL', 'LOG_FILE'],
    }

    for category, vars_in_category in categories.items():
        content_lines.append(f"# {category}")
        for var_name in vars_in_category:
            # Get value from environment or existing file
            value = os.getenv(var_name) or existing_vars.get(var_name, '')
            content_lines.append(f"{var_name}={value}")
        content_lines.append("")

    # Write the file
    with open(env_file, 'w') as f:
        f.write('\n'.join(content_lines))


def handle_help(args: argparse.Namespace) -> None:
    """Handle help command with comprehensive documentation."""
    if hasattr(args, 'topic') and args.topic:
        if args.topic == 'setup':
            _show_setup_help()
        elif args.topic == 'usage':
            _show_usage_help()
        elif args.topic == 'examples':
            _show_examples_help()
        elif args.topic == 'troubleshooting':
            _show_troubleshooting_help()
        else:
            _show_main_help()
    else:
        _show_main_help()

def _show_main_help() -> None:
    """Show main help information."""
    print("🤖 Personal Assistant & Life Coach - Help")
    print("=" * 50)
    print()
    print("COMMANDS:")
    print("  status          Show system status and memory contents")
    print("  init            Initialize memory directory")
    print("  chat            Interactive conversational mode")
    print("  query           AI-assisted suggestions and queries")
    print("  model           AI model management (list, select)")
    print("  config          Configuration management (init)")
    print("  goal            Goal management (add, list, update, model)")
    print("  task            Task management (add, list, update)")
    print("  journal         Journal entries (add, list)")
    print("  email           Email processing and analysis (process)")
    print()
    print("HELP TOPICS:")
    print("  help setup      Environment setup and prerequisites")
    print("  help usage      Detailed command usage")
    print("  help examples   Usage examples and workflows")
    print("  help troubleshooting  Common issues and solutions")
    print()
    print("GETTING STARTED:")
    print("  1. Run: assistant init")
    print("  2. Run: assistant status")
    print("  3. Try: assistant chat")
    print()
    print("Use 'assistant <command> --help' for command-specific help.")


def _show_setup_help() -> None:
    """Show setup and configuration help."""
    print("🔧 Setup & Configuration")
    print("=" * 30)
    print()
    print("PREREQUISITES:")
    print("  • Python 3.8+")
    print("  • Ollama server running locally or remotely")
    print("  • Network access to Ollama (if remote)")
    print()
    print("ENVIRONMENT VARIABLES:")
    print("  OLLAMA_URL=http://localhost:11434    # Ollama server URL")
    print("  OLLAMA_MODEL=llama2                   # Default model")
    print("  OLLAMA_TIMEOUT=120                    # Request timeout (seconds)")
    print("  MEMORY_DIR=~/.assistant/memory        # Memory storage location")
    print("  LOG_LEVEL=INFO                        # Logging verbosity")
    print()
    print("QUICK SETUP:")
    print("  export OLLAMA_URL=http://buntcomm.com:11434")
    print("  # Optional: Configure email processing")
    print("  export EMAIL_SERVER=imap.gmail.com")
    print("  export EMAIL_USERNAME=your.email@gmail.com")
    print("  export EMAIL_PASSWORD=your_password")
    print("  python assistant.py init")
    print("  python assistant.py status")
    print()
    print("MODEL SETUP:")
    print("  # List available models:")
    print("  python assistant.py goal model <model_name>")
    print("  ")
    print("  # Common models: llama2, codellama, mistral, vicuna")
    print()
    print("EMAIL SETUP:")
    print("  # Configure email processing (see AGENT.md)")
    print("  export EMAIL_SERVER=your.imap.server")
    print("  export EMAIL_USERNAME=your.username")
    print("  export EMAIL_PASSWORD=your.password")


def _show_usage_help() -> None:
    """Show detailed usage information."""
    print("📖 Detailed Usage Guide")
    print("=" * 25)
    print()
    print("MEMORY SYSTEM:")
    print("  The assistant uses append-only files for complete data integrity:")
    print("  • talaos.jsonl    - Goals and tasks in JSON Lines format")
    print("  • journal.md      - Reflections in Markdown with YAML frontmatter")
    print("  • changes.jsonl   - Complete audit trail of all modifications")
    print()
    print("COMMAND REFERENCE:")
    print()
    print("  assistant status")
    print("    Shows system status, memory contents, and configuration")
    print()
    print("  assistant init")
    print("    Creates memory directory and initializes empty files")
    print()
    print("  assistant chat [message]")
    print("    Starts interactive mode or sends a single message")
    print("    Commands: help, quit/exit/q")
    print()
    print("  assistant query <message>")
    print("    Gets AI suggestions or answers questions about your data")
    print("    Examples: 'what are my goals?', 'help me plan my day'")
    print()
    print("  assistant goal add <description> [--tags TAG...] [--priority PRIORITY]")
    print("    Adds a new goal directly (bypasses AI suggestions)")
    print()
    print("  assistant goal list")
    print("    Shows all current goals with status")
    print()
    print("  assistant goal update <goal_id> <status>")
    print("    Updates goal status (active, completed, cancelled)")
    print()
    print("  assistant goal model <model_name> [--timeout SECONDS]")
    print("    Changes the AI model (requires restart)")
    print()
    print("  assistant task add <description> [--goal GOAL_ID] [--tags TAG...]")
    print("    Adds a new task, optionally linked to a goal")
    print()
    print("  assistant task list")
    print("    Shows all current tasks with status")
    print()
    print("  assistant task update <task_id> <status>")
    print("    Updates task status (pending, in_progress, completed, cancelled)")
    print()
    print("  assistant journal add <content> [--type TYPE] [--tags TAG...]")
    print("    Adds a journal entry for reflection and tracking")
    print("    Types: reflection, gratitude, learning, goal_review, planning")
    print()
    print("  assistant journal list")
    print("    Shows recent journal entries")
    print()
    print("OPTIONS:")
    print("  --dry-run         Show what would happen without making changes")
    print("  --log-level LEVEL Set logging verbosity (DEBUG, INFO, WARNING, ERROR)")
    print("  --log-file FILE   Log to file instead of console")


def _show_examples_help() -> None:
    """Show usage examples and workflows."""
    print("💡 Usage Examples & Workflows")
    print("=" * 35)
    print()
    print("FIRST TIME SETUP:")
    print("  $ export OLLAMA_URL=http://buntcomm.com:11434")
    print("  $ python assistant.py init")
    print("  $ python assistant.py status")
    print()
    print("DAILY WORKFLOW:")
    print("  $ python assistant.py chat")
    print("  > What are my goals?")
    print("  > Help me plan today's tasks")
    print("  > Add reflection about my progress")
    print()
    print("GOAL MANAGEMENT:")
    print("  # Direct addition (fast)")
    print("  $ python assistant.py goal add 'Complete project milestone' --tags work --priority high")
    print("  ")
    print("  # AI-assisted planning")
    print("  $ python assistant.py query 'help me break down this big project'")
    print("  ")
    print("  # Check progress")
    print("  $ python assistant.py goal list")
    print()
    print("TASK TRACKING:")
    print("  $ python assistant.py task add 'Review requirements' --goal <goal_id> --tags planning")
    print("  $ python assistant.py task update <task_id> in_progress")
    print("  $ python assistant.py task list")
    print()
    print("REFLECTION & JOURNALING:")
    print("  $ python assistant.py journal add 'Made good progress today on the CLI implementation' --type reflection --tags work progress")
    print("  $ python assistant.py journal list")
    print()
    print("MODEL MANAGEMENT:")
    print("  $ python assistant.py model list")
    print("  $ python assistant.py model select")
    print("  $ export OLLAMA_MODEL=llama3.2:latest  # Set for current/future sessions")
    print("  $ python assistant.py config init      # Generate .env file")
    print("  $ python assistant.py goal model codellama --timeout 300")
    print()
    print("TROUBLESHOOTING:")
    print("  $ python assistant.py --log-level DEBUG status")
    print("  $ python assistant.py --dry-run goal add 'Test goal'")


def _show_troubleshooting_help() -> None:
    """Show troubleshooting information."""
    print("🔧 Troubleshooting Guide")
    print("=" * 25)
    print()
    print("COMMON ISSUES:")
    print()
    print("1. 'Cannot connect to Ollama server'")
    print("   • Check that Ollama is running: curl http://buntcomm.com:11434/api/tags")
    print("   • Verify OLLAMA_URL environment variable")
    print("   • Check network connectivity")
    print()
    print("2. 'Memory directory not found'")
    print("   • Run: python assistant.py init")
    print("   • Check write permissions in home directory")
    print()
    print("3. 'Invalid format specifier' errors")
    print("   • This is a known issue with mock responses in development")
    print("   • Real Ollama integration will resolve this")
    print()
    print("4. Goals/tasks not appearing")
    print("   • Check memory files: ~/.assistant/memory/")
    print("   • Verify JSON format in talaos.jsonl")
    print()
    print("5. Commands not working")
    print("   • Use: python assistant.py --help")
    print("   • Check Python version (3.8+ required)")
    print()
    print("DEBUGGING:")
    print("  • Verbose logging: --log-level DEBUG")
    print("  • File logging: --log-file assistant.log")
    print("  • Dry run mode: --dry-run (shows what would happen)")
    print()
    print("SYSTEM INFO:")
    print("  • Memory location: ~/.assistant/memory/")
    print("  • Config file: AGENT.md (contains secrets)")
    print("  • Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    print()
    print("GETTING HELP:")
    print("  • Run: python assistant.py help")
    print("  • Check: python assistant.py help troubleshooting")
    print("  • View logs with DEBUG level for detailed information")


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    if argv is None:
        argv = sys.argv[1:]

    try:
        # Parse arguments
        parser = setup_argparse()
        args = parser.parse_args(argv)

        # Set up logging
        log_level = args.log_level or config.log_level
        log_file = args.log_file or config.log_file
        setup_logging(level=log_level, log_file=log_file)

        logger.info("Personal Assistant starting")

        # Handle commands
        if args.command == 'status':
            handle_status(args)
        elif args.command == 'init':
            handle_init(args)
        elif args.command == 'chat':
            handle_chat(args)
        elif args.command == 'query':
            handle_query(args)
        elif args.command == 'model':
            handle_model(args)
        elif args.command == 'goal':
            handle_goal(args)
        elif args.command == 'task':
            handle_task(args)
        elif args.command == 'journal':
            handle_journal(args)
        elif args.command == 'email':
            handle_email(args)
        elif args.command == 'config':
            handle_config(args)
        elif args.command == 'help':
            handle_help(args)
        elif not args.command:
            # No command provided, show help
            parser.print_help()
            return 1
        else:
            print(f"❌ Unknown command: {args.command}")
            return 1

        logger.info("Personal Assistant completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("Goodbye! 👋")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1