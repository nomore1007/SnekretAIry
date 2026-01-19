#!/usr/bin/env python3
"""
End-to-end test script for the Personal Assistant.

Demonstrates the complete pipeline from query to change application.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from context import ContextBuilder
from proposals import ProposalEngine
from changes import MutationEngine
from ollama import OllamaClient

# Mock LLM response for testing (since Ollama may not be available)
MOCK_LLM_RESPONSE = """
Based on your request to help with project planning, I suggest the following:

1. Add a task for "Complete project requirements analysis" - this is crucial for good planning
2. Reflect on your current progress to maintain motivation

This will help you stay organized and track your achievements.

{
  "proposal_id": "test_planning_assistance",
  "reasoning": "Your query about project planning suggests you need structured task management and progress tracking.",
  "confidence": 0.85,
  "talaos_proposals": [
    {
      "action": "add_task",
      "content": "Complete project requirements analysis",
      "tags": ["work", "planning", "analysis"],
      "priority": "high"
    }
  ],
  "journal_proposals": [
    {
      "action": "add_entry",
      "content": "Today I focused on project planning and made progress on understanding the requirements.",
      "entry_type": "reflection",
      "tags": ["work", "progress", "planning"]
    }
  ]
}
"""

def demo_end_to_end():
    """Demonstrate the complete assistant workflow."""
    print("🤖 Personal Assistant - End-to-End Demo")
    print("=" * 50)

    # Step 1: Build context from user query
    print("\n📚 Step 1: Building Context")
    print("-" * 30)

    context_builder = ContextBuilder()
    query = "help me with project planning"
    context = context_builder.build_context(query, context_type="work")

    print(f"Query: '{query}'")
    print(f"Found {context['total_entries']} relevant memory entries")
    print(f"Context size: {context['context_size_chars']} characters")

    # Step 2: Parse LLM response into proposal
    print("\n📝 Step 2: Parsing AI Suggestions")
    print("-" * 30)

    proposal_engine = ProposalEngine()
    proposal = proposal_engine.parse_llm_output(MOCK_LLM_RESPONSE, query)

    print(f"Proposal ID: {proposal.proposal_id}")
    print(f"Confidence: {proposal.confidence_score:.1%}")
    print(f"Talaos changes: {len(proposal.talaos_proposals)}")
    print(f"Journal changes: {len(proposal.journal_proposals)}")

    # Step 3: Present proposal for user approval
    print("\n✅ Step 3: Proposal Review")
    print("-" * 30)

    presentation = proposal_engine.present_proposal(proposal)
    print(presentation)

    # Step 4: Apply changes (simulating user approval)
    print("\n🔄 Step 4: Applying Approved Changes")
    print("-" * 30)

    print("User input: y (approved)")

    mutation_engine = MutationEngine()
    results = mutation_engine.apply_changes_with_audit(proposal, user_approval=True)

    print(f"✅ Changes applied successfully: {results['success']}")
    print(f"📋 Talaos changes: {len([r for r in results['changes_applied'] if r['change_type'] == 'talaos'])}")
    print(f"📖 Journal changes: {len([r for r in results['changes_applied'] if r['change_type'] == 'journal'])}")

    if results['errors']:
        print(f"⚠️  Errors: {results['errors']}")

    # Step 5: Verify changes in memory
    print("\n🔍 Step 5: Verifying Memory Updates")
    print("-" * 30)

    # Check Talaos entries
    talaos_entries = context_builder.talaos.get_all_entries()
    recent_tasks = [e for e in talaos_entries if e['type'] == 'task'][-2:]  # Last 2 tasks

    print("Recent Tasks:")
    for task in recent_tasks:
        print(f"  • {task['content']} (status: {task['status']})")

    # Check Journal entries
    journal_entries = context_builder.journal.get_recent_entries(2)
    print("\nRecent Journal Entries:")
    for entry in journal_entries:
        frontmatter = entry['frontmatter']
        print(f"  • {frontmatter['type'].title()}: {entry['content'][:60]}...")

    # Step 6: Show audit trail
    print("\n📊 Step 6: Audit Trail")
    print("-" * 30)

    change_history = mutation_engine.get_change_history(5)
    print(f"Total changes recorded: {len(change_history)}")

    for change in change_history[:3]:  # Show last 3
        print(f"  • {change['change_id']}: {change['description']}")

    print("\n🎉 Demo Complete!")
    print("The assistant successfully processed your query, generated suggestions,")
    print("presented them for approval, and safely applied the changes to memory.")

def demo_context_only():
    """Demo just the context building (works without Ollama)."""
    print("📚 Context Builder Demo")
    print("=" * 30)

    context_builder = ContextBuilder()

    queries = [
        "work project planning",
        "personal health goals",
        "career development"
    ]

    for query in queries:
        print(f"\nQuery: '{query}'")
        context = context_builder.build_context(query)
        print(f"  → Found {context['total_entries']} entries")
        print(f"  → Context size: {context['context_size_chars']} chars")

def main():
    """Main demo function."""
    # Check for required environment variable
    import os
    if not os.getenv('OLLAMA_URL'):
        print("❌ Error: OLLAMA_URL environment variable not set")
        print("See AGENT.md for the correct URL to use")
        sys.exit(1)

    if len(sys.argv) > 1 and sys.argv[1] == "--context-only":
        demo_context_only()
    else:
        demo_end_to_end()

if __name__ == "__main__":
    main()