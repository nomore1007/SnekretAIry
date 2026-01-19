# 🛠️ Development Guide

This guide provides comprehensive information for developers working on the Personal Assistant project.

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Development Setup](#development-setup)
- [Code Organization](#code-organization)
- [Adding New Features](#adding-new-features)
- [Testing Strategy](#testing-strategy)
- [Debugging Techniques](#debugging-techniques)
- [Performance Considerations](#performance-considerations)
- [Security Guidelines](#security-guidelines)

## 🏗️ Architecture Overview

### Core Design Principles

1. **Append-Only Memory**: All data operations preserve existing information
2. **User Sovereignty**: AI suggests, humans approve all changes
3. **Security First**: No destructive operations, input validation, audit trails
4. **CLI-First Design**: Command-line interface with optional interactive modes
5. **Modular Architecture**: Clear separation of concerns, dependency injection

### System Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                 CLI Interface                       │    │
│  │  • Command parsing and routing                      │    │
│  │  • Interactive conversation mode                    │    │
│  │  • Help system and user guidance                    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────┬───────────────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼───┐   ┌─────▼─────┐   ┌───▼───┐
│Config │   │Application│   │External│
│Manager│   │  Logic    │   │Services│
│       │   │           │   │        │
│• Env  │   │• Context  │   │• Ollama│
│  vars │   │  Builder  │   │  Client│
│• Val- │   │• Proposal │   │• File  │
│  idation│ │  Engine   │   │  system│
└───────┘   └─────┬─────┘   └────────┘
                  │
         ┌────────▼────────┐
         │                 │
    ┌────▼────┐   ┌────────▼───────┐
    │  Memory │   │   Change       │
    │ Managers│   │   Application  │
    │         │   │                │
    │• Talaos │   │• Mutation      │
    │  (Goals) │   │  Engine       │
    │• Journal│   │• Audit Trails  │
    │  (Refl.) │   │• Safety Checks │
    └─────────┘   └────────────────┘
```

### Data Flow Patterns

1. **Direct Commands**: CLI → Memory Managers → File Operations
2. **AI-Assisted**: CLI → Context Builder → Ollama → Proposal Engine → User Approval → Change Application
3. **Queries**: CLI → Context Builder → Memory Search → Formatted Response

## 🚀 Development Setup

### Prerequisites

- Python 3.8+ with pip
- Ollama server (local or remote)
- Git for version control
- Terminal with ANSI color support

### Environment Setup

1. **Clone and enter project:**
   ```bash
   git clone <repository>
   cd personal-assistant
   ```

2. **Set required environment variables:**
   ```bash
   # Required (see AGENT.md for actual URL)
   export OLLAMA_URL=http://buntcomm.com:11434

   # Optional customizations
   export OLLAMA_MODEL=llama2
   export OLLAMA_TIMEOUT=120
   export MEMORY_DIR=~/dev/assistant-data
   export LOG_LEVEL=DEBUG
   ```

3. **Initialize development environment:**
   ```bash
   python assistant.py init
   python assistant.py status
   ```

### Development Workflow

1. **Create feature branch:**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes following patterns in existing code**

3. **Test thoroughly:**
   ```bash
   # Syntax check
   python -m py_compile src/**/*.py

   # Dry run tests
   python assistant.py --dry-run --log-level DEBUG status

   # Interactive testing
   python assistant.py chat  # Manual testing
   ```

4. **Update documentation:**
   - Code docstrings
   - Help system in CLI
   - README if needed
   - This development guide

5. **Commit with clear messages:**
   ```bash
   git commit -m "feat: add my new feature

   - Added new capability to handle X
   - Updated CLI help system
   - Added comprehensive tests"
   ```

## 📁 Code Organization

### Directory Structure

```
src/
├── cli/                    # Command-line interface
│   └── __init__.py        # Main CLI logic, argument parsing, help system
├── config/                 # Configuration management
│   └── __init__.py        # Environment variables, validation, Config class
├── memory/                 # File-based memory systems
│   ├── __init__.py        # Common memory interfaces
│   ├── talaos.py          # Goal/task management (JSONL format)
│   └── journal.py         # Reflection entries (Markdown+YAML)
├── context/                # Context building and filtering
│   └── __init__.py        # ContextBuilder class, relevance algorithms
├── ollama/                 # AI integration
│   ├── __init__.py        # OllamaClient interface
│   └── client.py          # HTTP client, response parsing, validation
├── proposals/              # AI suggestion processing
│   └── __init__.py        # ProposalEngine, validation, user presentation
├── changes/                # Safe change application
│   └── __init__.py        # MutationEngine, audit trails, safety checks
└── utils/                  # Shared utilities
    ├── __init__.py        # Common imports
    ├── logging.py         # Structured logging setup
    └── timestamps.py      # ISO 8601 timestamp handling
```

### Module Responsibilities

| Module | Responsibility | Key Classes |
|--------|----------------|-------------|
| `cli` | User interaction, command routing | CLI handlers, InteractiveAssistant |
| `config` | Configuration management | Config class, validation |
| `memory` | Data persistence | TalaosManager, JournalManager |
| `context` | Data retrieval and filtering | ContextBuilder |
| `ollama` | AI communication | OllamaClient, error handling |
| `proposals` | AI output processing | ProposalEngine, validation |
| `changes` | Safe data modification | MutationEngine, audit trails |
| `utils` | Shared functionality | Logging, timestamps |

### Import Patterns

```python
# Absolute imports only
from config import config
from memory import TalaosManager
from utils import get_logger

# No relative imports
# No wildcard imports
# Explicit imports for clarity
```

### Naming Conventions

- **Modules**: `lowercase_with_underscores.py`
- **Classes**: `PascalCase`
- **Functions/Methods**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`

## ✨ Adding New Features

### Adding a New Command

1. **Define command arguments** in `setup_argparse()`:
   ```python
   # Add to subparsers section
   my_parser = subparsers.add_parser('mycommand', help='My new command')
   my_parser.add_argument('required_arg', help='Required argument')
   my_parser.add_argument('--optional', default='value', help='Optional argument')
   ```

2. **Create handler function**:
   ```python
   def handle_mycommand(args: argparse.Namespace) -> None:
       """
       Handle my new command.

       Args:
           args: Parsed command-line arguments
       """
       logger.info(f"Executing mycommand with arg: {args.required_arg}")

       # Implementation here
       result = perform_operation(args.required_arg, args.optional)

       if result.success:
           print(f"✅ {result.message}")
       else:
           print(f"❌ {result.error}")
   ```

3. **Register handler** in `main()`:
   ```python
   elif args.command == 'mycommand':
       handle_mycommand(args)
   ```

4. **Update help system**:
   ```python
   # Add to _show_main_help()
   print("  mycommand       My new command description")

   # Add detailed help in _show_usage_help()
   print("  assistant mycommand <arg> [--optional VALUE]")
   print("    Description of what the command does")
   ```

### Adding Memory Types

1. **Create new manager class**:
   ```python
   class NewMemoryManager:
       def __init__(self, memory_dir: str):
           self.memory_dir = Path(memory_dir)
           self.data_file = self.memory_dir / "newdata.jsonl"

       def add_entry(self, content: str) -> str:
           # Implementation
           pass

       def get_entries(self) -> List[Dict]:
           # Implementation
           pass
   ```

2. **Update memory module**:
   ```python
   # src/memory/__init__.py
   from .newmanager import NewMemoryManager
   __all__ = ['TalaosManager', 'JournalManager', 'NewMemoryManager']
   ```

3. **Integrate with context builder**:
   ```python
   # Add to ContextBuilder
   self.new_memory = NewMemoryManager(self.memory_dir)
   ```

### Adding AI Capabilities

1. **Extend Ollama client** if needed for new model features

2. **Update proposal engine** for new suggestion types:
   ```python
   # Add new proposal type
   @dataclass
   class NewProposal:
       action: str = "new_action"
       # ... fields

   # Update validation and application logic
   ```

3. **Update context builder** for new data types

## 🧪 Testing Strategy

### Testing Levels

1. **Unit Tests**: Individual functions and classes
2. **Integration Tests**: Module interactions
3. **End-to-End Tests**: Complete user workflows
4. **Manual Tests**: Interactive exploration

### Testing Commands

```bash
# Syntax validation
python -m py_compile src/**/*.py

# Dry run testing (safe, no data changes)
python assistant.py --dry-run <command>

# Debug logging
python assistant.py --log-level DEBUG --log-file test.log <command>

# Memory integrity checks
python assistant.py status
cat ~/.assistant/memory/*.jsonl | head -10
```

### Test Scenarios

**Core Functionality:**
- Memory initialization and file creation
- Goal/task addition, listing, status updates
- Journal entry creation and retrieval
- Context building and relevance filtering

**AI Integration:**
- Ollama connection and model detection
- Prompt generation and response parsing
- Proposal creation and validation
- User approval workflow

**Error Conditions:**
- Network failures and timeouts
- Invalid data formats
- File permission issues
- Memory corruption scenarios

**Edge Cases:**
- Empty memory files
- Very large context requests
- Concurrent operations (if applicable)
- System resource constraints

## 🔍 Debugging Techniques

### Logging Levels

```bash
# Development debugging
python assistant.py --log-level DEBUG status

# File logging for analysis
python assistant.py --log-file debug.log --log-level DEBUG chat

# Production logging
export LOG_LEVEL=INFO  # Default
export LOG_LEVEL=WARNING  # Reduce verbosity
```

### Common Debug Patterns

1. **Check environment:**
   ```bash
   echo "OLLAMA_URL: $OLLAMA_URL"
   echo "MEMORY_DIR: $MEMORY_DIR"
   curl -s $OLLAMA_URL/api/tags | head -5
   ```

2. **Inspect memory files:**
   ```bash
   ls -la ~/.assistant/memory/
   wc -l ~/.assistant/memory/*.jsonl
   tail -5 ~/.assistant/memory/talaos.jsonl
   ```

3. **Test individual components:**
   ```python
   from config import config
   from memory import TalaosManager
   from ollama import OllamaClient

   print("Config:", config.ollama_url)
   talaos = TalaosManager()
   print("Goals:", len(talaos.get_goals()))
   ```

4. **Network debugging:**
   ```bash
   # Test Ollama connectivity
   time curl -v $OLLAMA_URL/api/generate \
     -H "Content-Type: application/json" \
     -d '{"model":"llama2","prompt":"test","stream":false}'
   ```

### Performance Profiling

```python
import cProfile
import pstats

# Profile a function
profiler = cProfile.Profile()
profiler.enable()

# Code to profile
result = expensive_operation()

profiler.disable()
stats = pstats.Stats(profiler).sort_stats('cumulative')
stats.print_stats(10)  # Top 10 time consumers
```

## ⚡ Performance Considerations

### Current Performance Characteristics

- **Memory Operations**: O(n) for reads, O(1) for appends
- **Context Building**: O(n) filtering with relevance scoring
- **AI Requests**: Network-bound, configurable timeouts
- **File I/O**: Optimized for personal-scale data (thousands of entries)

### Optimization Opportunities

1. **Memory Indexing**: Add indexes for frequent queries
2. **Caching**: Cache parsed memory data in memory
3. **Batch Operations**: Group multiple small writes
4. **Async I/O**: Non-blocking file operations for large datasets
5. **Compression**: Compress old memory entries

### Scalability Limits

- **Memory Size**: Tested with ~10,000 entries
- **Context Size**: Limited to 4000 tokens (~12,000 chars)
- **Concurrent Users**: Single-user design
- **Network Dependency**: Offline functionality limited

## 🔒 Security Guidelines

### Core Security Principles

1. **No Data Destruction**: Append-only operations only
2. **User Consent**: All changes require explicit approval
3. **Input Validation**: All inputs validated and sanitized
4. **Credential Management**: Secrets in AGENT.md only
5. **Audit Trails**: Complete change history maintained

### Secure Coding Practices

```python
# Input validation
def validate_input(data: str) -> bool:
    if not data or len(data) > MAX_LENGTH:
        return False
    # Additional validation logic
    return True

# Safe file operations
def safe_write(path: Path, content: str) -> None:
    # Create temp file first
    temp_path = path.with_suffix('.tmp')
    with open(temp_path, 'w') as f:
        f.write(content)
    # Atomic move
    temp_path.replace(path)

# Error handling without information leakage
try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise ValueError("Operation failed - check logs for details")
```

### Security Checklist

- [ ] No hardcoded secrets or credentials
- [ ] Input validation on all user data
- [ ] Safe file path handling (no .. or absolute paths)
- [ ] Network timeouts and error handling
- [ ] Audit logging of all operations
- [ ] No destructive file operations
- [ ] User approval for all changes
- [ ] Data integrity validation

### Threat Model

**Attack Vectors Considered:**
- File system access (limited to designated directory)
- Network interception (HTTPS recommended)
- Data corruption (append-only design prevents)
- AI prompt injection (input validation and user approval)
- Resource exhaustion (timeouts and limits)

**Mitigations:**
- Restricted file operations
- Input sanitization
- User confirmation workflows
- Comprehensive logging
- Fail-safe error handling

---

## 📚 Additional Resources

- **AGENT.md**: Constitutional documentation and architectural decisions
- **README.md**: User-facing documentation
- **TESTING.md**: Testing instructions and examples
- **Ollama Documentation**: https://github.com/jmorganca/ollama

Remember: **This is personal software** - it should enhance human agency, not replace it. All AI suggestions require human approval and judgment.</content>
<parameter name="filePath">DEVELOPMENT.md