# AGENT.md - Constitutional Documentation

## Project Intent

This project implements a file-based personal assistant and life coach that leverages remote Ollama integration for intelligent suggestions while maintaining complete user control and data integrity.

**Core Purpose**: Provide AI-assisted personal development support through structured goal tracking (Talaos) and reflective journaling, with all changes requiring explicit user approval.

**Key Principles**:
- Memory as append-only narrative, never mutable state
- User sovereignty over all data and decisions
- Security-first design with clear boundaries
- Production-quality code suitable for public GitHub release

## Non-Goals

- Real-time collaboration or multi-user support
- Integration with external productivity platforms
- Automated scheduling or calendar management
- Voice-based interactions
- Mobile or web UI (CLI-first design)
- Model-specific optimizations or hardcoding
- Destructive file operations or data deletion

## Architecture Decisions from Phase 0

### Language: Python
- CLI excellence with argparse/click libraries
- Native file I/O and text processing capabilities
- Robust HTTP client libraries for Ollama integration
- Rich ecosystem for testing, logging, and configuration
- Cross-platform compatibility (Windows/macOS/Linux)

### Architectural Style: Modular CLI Application with Command Pattern
- Clear separation of concerns with dedicated modules
- Configuration-driven approach for security
- Pipeline pattern: validation → processing → confirmation → application
- Error boundaries at each architectural layer

### File Formats
**Talaos (Goals/Tasks)**: JSON Lines format with timestamped entries
- Structured data supporting task/goal relationships
- Append-only friendly (one JSON object per line)
- Supports querying, filtering, and extensibility
- Human-readable for debugging

**Journal (Reflections)**: Markdown with YAML frontmatter
- Narrative format for personal reflections
- Rich formatting while remaining text-based
- Frontmatter provides structured metadata
- Append-only by design

### High-Level Architecture
```
CLI Interface → Config Manager
                   ↓
Core Engine ← Ollama Client
     ↓
Context Builder → Proposal Engine
     ↓
Talaos Manager ← Journal Manager ← Change Applier
```

### Security Boundaries
1. Network isolation: Only configured Ollama endpoint accessible
2. File operation safety: All memory operations append-only
3. Input validation: LLM responses validated before processing
4. User confirmation: No automated changes without explicit approval
5. Credential management: Ollama URL via environment variables only
6. Error containment: Module failures don't compromise others

## Configuration Management

### Settings File (.env)

The assistant uses a `.env` file to persist configuration across sessions. This file contains all environment variables and is automatically loaded on startup.

#### Creating/Updating the Settings File
```bash
# Generate .env file with current environment variables
python assistant.py config init

# Or create manually by copying .env.example
cp .env.example .env
```

#### Security Note
⚠️ **IMPORTANT**: The `.env` file may contain sensitive information (passwords, API keys). It is:
- Added to `.gitignore` to prevent accidental commits
- Never shared or committed to version control
- Stored locally on your system only

### Environment Variables

#### Ollama Configuration
- `OLLAMA_URL`: Ollama server endpoint (required)
- `OLLAMA_MODEL`: Default AI model (default: `llama2`)
- `OLLAMA_TIMEOUT`: Request timeout in seconds (default: `120`)

#### Email Configuration
- `EMAIL_SERVER`: IMAP server address (e.g., `imap.gmail.com`)
- `EMAIL_PORT`: IMAP server port (default: `993`)
- `EMAIL_USERNAME`: Email account username
- `EMAIL_PASSWORD`: Email account password
- `EMAIL_SSL`: Use SSL connection (default: `true`)
- `EMAIL_DAYS_BACK`: Days of email history to process (default: `7`)

#### Memory Configuration
- `MEMORY_DIR`: Memory file storage location (default: `~/.assistant/memory`)
- `MAX_CONTEXT_SIZE`: Maximum context tokens (default: `4000`)

#### Logging Configuration
- `LOG_LEVEL`: Logging verbosity (default: `INFO`)
- `LOG_FILE`: Optional log file path (default: console only)

### Email Security Notes
⚠️ **Important**: Email passwords stored in the `.env` file pose a security risk. Consider using:
- Secure credential management systems
- Environment-specific credential files
- OAuth authentication (future enhancement)
- Short-lived tokens instead of permanent passwords

### Example .env Setup
```bash
# Ollama Configuration
OLLAMA_URL=http://buntcomm.com:11434
OLLAMA_MODEL=llama3.2:latest
OLLAMA_TIMEOUT=120

# Email Configuration (leave empty if not using)
EMAIL_SERVER=imap.gmail.com
EMAIL_PORT=993
EMAIL_USERNAME=your.email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_SSL=true
EMAIL_DAYS_BACK=7

# Memory Configuration
MEMORY_DIR=~/.assistant/memory
MAX_CONTEXT_SIZE=4000

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=
```

## Coding Standards

### Python Version
- Target: Python 3.8+
- Use modern Python features (f-strings, dataclasses, type hints)
- No legacy Python 2 compatibility

### Code Organization
```
src/
├── cli/              # Command-line interface
├── core/             # Main orchestration logic
├── config/           # Configuration management
├── ollama/           # LLM integration
├── memory/           # File-based memory management
│   ├── talaos.py    # Goal/task management
│   └── journal.py   # Reflection management
├── context/          # Context building and filtering
├── proposals/        # Change proposal generation
├── changes/          # Safe change application
└── utils/            # Shared utilities
```

### Naming Conventions
- Modules: lowercase with underscores (`memory_manager.py`)
- Classes: PascalCase (`ContextBuilder`)
- Functions/Methods: snake_case (`build_context()`)
- Constants: UPPER_SNAKE_CASE (`DEFAULT_TIMEOUT`)
- Private members: leading underscore (`_internal_method()`)

### Type Hints
- Use full type annotations for all public APIs
- Include return types for all functions
- Use `typing` module for complex types
- Document complex type decisions in docstrings

### Error Handling
- Custom exception hierarchy for domain-specific errors
- Never catch broad `Exception` - be specific
- Log errors with appropriate levels (DEBUG, INFO, WARNING, ERROR)
- Fail fast for configuration or initialization errors
- Graceful degradation for runtime issues

### Testing
- Unit tests for all modules with pytest
- Integration tests for end-to-end workflows
- Mock external dependencies (Ollama, file system)
- Test both success and failure paths
- Minimum 80% code coverage target

### Logging
- Structured logging with context
- Appropriate log levels for different environments
- Never log sensitive information
- Include timestamps and module names

## Security Standards

### Input Validation
- Validate all user inputs at boundaries
- Sanitize file paths to prevent directory traversal
- Validate JSON/YAML parsing results
- Check LLM response structure before processing

### Secrets Management
- Ollama endpoint URL: `http://buntcomm.com:11434` (stored only in AGENT.md)
- Environment variable `OLLAMA_URL` must be set to the above URL
- Email credentials stored in environment variables (see below)
- No hardcoded credentials or API keys in source code
- Validate URL format and scheme (http/https)
- Support for authentication if required by Ollama server

### File Operations
- All memory file operations are append-only
- Never delete, overwrite, or truncate existing data
- Use atomic writes for new entries
- Validate file permissions before operations
- Backup critical operations (when safe to do so)

### Network Security
- HTTPS preferred for Ollama communication
- Configurable timeouts to prevent hanging
- Validate SSL certificates
- Rate limiting considerations for LLM calls

## AI Usage Rules

### LLM Integration Guidelines
- Treat LLM as suggestion engine, not decision maker
- All changes require explicit user confirmation
- Validate LLM responses against expected schemas
- Implement fallback behavior for LLM failures
- Abstract model choice - no hardcoded model assumptions

### Context Management
- Never send full memory files to LLM
- Extract relevant context based on user query
- Implement size limits and summarization
- Separate work vs personal context domains
- Prefer relevance over completeness

### Response Processing
- Parse LLM output into structured proposals
- Validate proposal structure and safety
- Present proposals clearly for user review
- Allow user to modify proposals before approval
- Log all LLM interactions for audit trail

### Safety Boundaries
- LLM cannot directly modify files
- LLM cannot execute system commands
- LLM cannot access network resources beyond Ollama
- All LLM suggestions are proposals, not actions

## Runtime Restrictions

### Forbidden Operations
- Never reference this AGENT.md file at runtime
- Never perform destructive file operations
- Never execute code suggested by LLM
- Never access internet beyond configured Ollama endpoint
- Never store or cache LLM responses beyond session
- Never modify system configuration or environment

### Data Integrity
- All memory operations preserve existing data
- Changes are timestamped with ISO 8601 format
- Audit trail maintained for all modifications
- Files remain human-readable for emergency access
- Backup strategies for critical data

### User Experience
- CLI-first design with clear command structure
- Interactive mode for conversational workflows
- Dry-run/preview mode for all operations
- Clear error messages and recovery instructions
- Progress indicators for long-running operations

## Change Log

This section records all significant changes to the project architecture, requirements, or implementation approach. All entries are append-only.

### 2024-01-19: Project Initialization
- Completed Phase 0 analysis and architectural decisions
- Established Python as implementation language
- Defined JSONL format for Talaos, Markdown+YAML for Journal
- Created modular CLI architecture with security boundaries
- Documented coding standards and AI usage rules

### Future Entries
- [Date]: [Description of change and rationale]</content>
<parameter name="filePath">AGENT.md