# How to Run and Test the Personal Assistant

## Prerequisites

1. **Python 3.8+** installed
2. **Ollama server** running (see AGENT.md for URL)
3. **Environment variable** set: `export OLLAMA_URL=http://buntcomm.com:11434`

## Quick Start

```bash
# Set the environment variable (see AGENT.md for the exact URL)
export OLLAMA_URL=http://buntcomm.com:11434

# Check status
python assistant.py status

# Run context-only demo (works without Ollama)
python demo.py --context-only

# Run full end-to-end demo (requires Ollama)
python demo.py
```

## Testing the Components

### 1. Memory Systems
```bash
# Test Talaos (goals/tasks)
python3 -c "
import sys; sys.path.insert(0, 'src')
from memory import TalaosManager
t = TalaosManager()
goal_id = t.add_goal('Test goal')
print(f'Added goal: {goal_id}')
"

# Test Journal
python3 -c "
import sys; sys.path.insert(0, 'src')
from memory import JournalManager
j = JournalManager()
timestamp = j.add_entry('Test entry')
print(f'Added entry: {timestamp}')
"
```

### 2. Context Building
```bash
export OLLAMA_URL=http://buntcomm.com:11434
python3 -c "
import sys; sys.path.insert(0, 'src')
from context import ContextBuilder
cb = ContextBuilder()
context = cb.build_context('project planning')
print(f'Found {context[\"total_entries\"]} relevant entries')
"
```

### 3. Proposal Engine
```bash
export OLLAMA_URL=http://buntcomm.com:11434
python3 -c "
import sys; sys.path.insert(0, 'src')
from proposals import ProposalEngine
pe = ProposalEngine()
proposal = pe.parse_llm_output('Add a task for testing', 'test query')
print(f'Parsed proposal with {len(proposal.talaos_proposals)} changes')
"
```

## Architecture Overview

The assistant follows a secure, append-only architecture:

- **Memory Layer**: Talaos (JSONL) + Journal (Markdown+YAML)
- **Context Layer**: Intelligent relevance-based selection
- **Proposal Layer**: LLM output parsing with safety validation
- **Mutation Layer**: Audited change application with user approval
- **CLI Layer**: User interaction and command processing

All changes require explicit user approval and maintain full audit trails.

## Security Notes

- Ollama URL stored only in AGENT.md (not in code)
- All memory operations are append-only
- User confirmation required for changes
- No destructive operations allowed
- Comprehensive input validation