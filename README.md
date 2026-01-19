# SnekretAIry - Personal AI Assistant & Life Coach

A sophisticated personal assistant that leverages AI to help manage goals, track progress, and provide intelligent insights through natural conversation.

## ✨ Features

- **🤖 AI-Powered Conversations**: Natural language interactions with context-aware responses
- **🎯 Goal & Task Management**: Structured goal tracking with AI-assisted planning
- **📖 Personal Journaling**: Reflective writing with AI-powered insights
- **📧 Email Processing**: Automatic email analysis with news briefs and todo generation
- **🔄 Change Tracking**: Complete audit trail of all modifications
- **🔒 Secure Configuration**: Environment-based settings with sensitive data protection

## 🏗️ Architecture

```
CLI Interface → Config Manager
                   ↓
Core Engine ← Ollama Client
     ↓
Context Builder → Proposal Engine
     ↓
Talaos Manager ← Journal Manager ← Change Applier
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Ollama server running locally or remotely
- Internet connection for Ollama API

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/SnekretAIry.git
   cd SnekretAIry
   ```

2. **Set up environment:**
   ```bash
   # Copy the example configuration
   cp .env.example .env

   # Edit .env with your settings
   nano .env
   ```

3. **Configure required settings:**
   ```bash
   # Required: Ollama server URL
   OLLAMA_URL=http://localhost:11434

   # Optional: Email processing
   EMAIL_SERVER=your.imap.server
   EMAIL_USERNAME=your.email@domain.com
   EMAIL_PASSWORD=your_password
   ```

4. **Initialize the assistant:**
   ```bash
   python assistant.py init
   ```

## 📖 Usage

### Basic Commands

```bash
# Check system status
python assistant.py status

# Start interactive conversation
python assistant.py chat

# Get AI suggestions
python assistant.py query "Help me plan my day"

# Manage goals and tasks
python assistant.py goal add "Complete project milestone"
python assistant.py task add "Review requirements" --goal <goal_id>

# Process emails
python assistant.py email process

# Manage AI models
python assistant.py model list
python assistant.py model select
```

### Configuration Management

```bash
# Generate/update .env file
python assistant.py config init

# List available AI models
python assistant.py model list

# Select and persist a model
python assistant.py model select --persist
```

## 📋 Configuration

### Environment Variables (.env file)

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_URL` | Ollama server endpoint | Required |
| `OLLAMA_MODEL` | Default AI model | `llama2` |
| `OLLAMA_TIMEOUT` | Request timeout (seconds) | `120` |
| `EMAIL_SERVER` | IMAP server address | - |
| `EMAIL_USERNAME` | Email account username | - |
| `EMAIL_PASSWORD` | Email account password | - |
| `MEMORY_DIR` | Memory storage location | `~/.assistant/memory` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

### Memory Structure

```
~/.assistant/memory/
├── telos.jsonl        # Goals and tasks
├── journal.md         # Reflections with YAML metadata
└── changes.jsonl      # Complete audit trail
```

## 🤖 AI Integration

### Supported Models

The assistant works with any Ollama-compatible model. Popular choices:

- **General Purpose**: `llama3.2:latest`, `llama3.2:1b`
- **Coding**: `qwen2.5-coder:7b`, `codellama`
- **Lightweight**: `smollm2:135m`, `tinyllama:latest`
- **Specialized**: Various fine-tuned models available

### Model Selection

```bash
# List available models
python assistant.py model list

# Interactive selection
python assistant.py model select

# Persist selection
python assistant.py model select --persist
```

## 📧 Email Integration

### Setup

1. **Configure email settings in `.env`:**
   ```bash
   EMAIL_SERVER=imap.gmail.com
   EMAIL_USERNAME=your.email@gmail.com
   EMAIL_PASSWORD=your_app_password  # Use app password for Gmail
   EMAIL_SSL=true
   EMAIL_DAYS_BACK=7
   ```

2. **Process emails:**
   ```bash
   python assistant.py email process
   ```

### Features

- **Automatic Analysis**: AI-powered email summarization
- **News Briefs**: Key information extraction
- **Todo Generation**: Actionable items from emails
- **Deduplication**: Prevents reprocessing of analyzed emails

## 🛡️ Security & Privacy

### Data Protection

- **Append-Only Memory**: No destructive operations
- **Environment Variables**: Sensitive data not in code
- **Git Exclusion**: `.env` files never committed
- **Audit Trail**: Complete change history

### Best Practices

- Use app passwords instead of main account passwords
- Regularly review your `.env` file
- Keep Ollama server access restricted
- Backup your memory directory

## 🔧 Development

### Project Structure

```
src/
├── cli/              # Command-line interface
├── config/           # Configuration management
├── ollama/           # AI model integration
├── memory/           # Data persistence
│   ├── telos.py      # Goal/task management
│   └── journal.py    # Reflection management
├── context/          # Context building
├── proposals/        # AI suggestion generation
├── changes/          # Safe change application
└── email_integration/# Email processing
```

### Adding New Features

1. **Commands**: Add to `src/cli/__init__.py`
2. **Modules**: Create in appropriate `src/` subdirectory
3. **Configuration**: Update `src/config/__init__.py`
4. **Documentation**: Update this README

### Testing

```bash
# Run with dry-run mode
python assistant.py --dry-run <command>

# Check logs
python assistant.py --log-level DEBUG <command>
```

## 📝 API Reference

### Core Classes

- **CLI**: Command-line interface and argument parsing
- **OllamaClient**: AI model communication
- **TelosManager**: Goal and task management
- **JournalManager**: Reflection and journaling
- **EmailProcessor**: Email analysis and processing

### Data Formats

- **Telos**: JSON Lines format for goals/tasks
- **Journal**: Markdown with YAML frontmatter
- **Changes**: JSON Lines audit trail

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is open source. See LICENSE file for details.

## 🙏 Acknowledgments

- Built with [Ollama](https://ollama.ai/) for AI integration
- Inspired by personal productivity methodologies
- Designed for security-first AI assistance

---

**SnekretAIry** - Your AI companion for personal growth and productivity.