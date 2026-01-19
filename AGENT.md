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
- [Date]: [Description of change and rationale]

## Developer Guidelines

This section provides comprehensive guidelines for AI agents and human developers working in this repository. It includes build/lint/test commands, code style conventions, and operational procedures.

### Build, Lint, and Test Commands

#### Build Commands
```bash
# Full build
npm run build

# Development build with watch mode
npm run dev

# Production build
npm run build:prod

# Clean and rebuild
npm run clean && npm run build
```

#### Lint Commands
```bash
# Lint all files
npm run lint

# Lint and auto-fix issues
npm run lint:fix

# Lint specific files
npx eslint src/components/Button.tsx src/utils/helpers.ts

# Type checking
npm run typecheck

# Format code
npm run format
```

#### Test Commands
```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run specific test file
npm test -- tests/unit/Button.test.tsx

# Run tests matching pattern
npm test -- --testNamePattern="should handle click"

# Run tests for specific component/function
npm test -- --testPathPattern=Button

# Run integration tests only
npm run test:integration

# Run e2e tests
npm run test:e2e

# Debug specific test
npm test -- --inspect-brk tests/unit/Button.test.tsx
```

#### Development Workflow
```bash
# Start development server
npm run dev

# Run pre-commit checks
npm run pre-commit

# Generate documentation
npm run docs

# Run security audit
npm audit

# Update dependencies
npm update

# Check bundle size
npm run analyze
```

### Code Style Guidelines

#### General Principles
- Write clean, readable, and maintainable code
- Follow DRY (Don't Repeat Yourself) principle
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions small and focused (single responsibility)
- Use early returns to reduce nesting
- Prefer const over let, avoid var
- Use descriptive commit messages

#### File Organization
```
src/
├── components/          # Reusable UI components
├── pages/              # Page components
├── hooks/              # Custom React hooks
├── utils/              # Utility functions
├── services/           # API and external service calls
├── types/              # TypeScript type definitions
├── constants/          # Application constants
├── styles/             # Global styles and themes
└── assets/             # Static assets
```

#### Naming Conventions

##### Components
- Use PascalCase for component names: `UserProfile.tsx`
- File names match component names: `Button.tsx` exports `Button`
- Use descriptive names: `UserList` instead of `List`

##### Functions and Variables
- Use camelCase: `getUserData()`, `userName`, `isLoading`
- Boolean variables: `isEnabled`, `hasError`, `canSubmit`
- Event handlers: `handleClick`, `onUserSelect`
- Private/internal: prefix with underscore `_internalFunction`

##### Files and Directories
- Use kebab-case for files: `user-profile.tsx`
- Use camelCase for directories: `userManagement`
- Test files: `Component.test.tsx`, `utils.test.ts`
- Index files: `index.ts` for barrel exports

##### Constants
- Use UPPER_SNAKE_CASE: `MAX_RETRY_COUNT`, `API_BASE_URL`
- Group related constants in objects: `export const COLORS = { primary: '#007bff' }`

### TypeScript Guidelines

#### Type Definitions
```typescript
// Good: Explicit types
interface User {
  id: number;
  name: string;
  email: string;
  createdAt: Date;
}

// Prefer interfaces over types for object shapes
// Use types for unions, primitives, etc.
type Status = 'active' | 'inactive' | 'pending';
type UserId = number;
```

#### Function Signatures
```typescript
// Good: Explicit return types for exported functions
export function calculateTotal(items: CartItem[]): number {
  return items.reduce((sum, item) => sum + item.price, 0);
}

// Good: Use union types for multiple possible types
function formatValue(value: string | number): string {
  return typeof value === 'string' ? value : value.toString();
}
```

#### Generics
```typescript
// Good: Use generics for reusable components
interface ApiResponse<T> {
  data: T;
  error?: string;
  loading: boolean;
}

function fetchUser<T extends User>(id: number): Promise<ApiResponse<T>> {
  // implementation
}
```

### React Guidelines

#### Component Structure
```tsx
// Good: Functional component with proper typing
interface ButtonProps {
  children: React.ReactNode;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
  disabled?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  onClick,
  variant = 'primary',
  disabled = false
}) => {
  return (
    <button
      className={`btn btn-${variant}`}
      onClick={onClick}
      disabled={disabled}
    >
      children
    </button>
  );
};
```

#### Hooks Usage
- Use custom hooks for reusable logic
- Follow rules of hooks strictly
- Name custom hooks with 'use' prefix: `useLocalStorage`
- Keep hooks simple and focused

#### State Management
```tsx
// Good: Use useState for local component state
const [count, setCount] = useState(0);

// Good: Use useReducer for complex state logic
const [state, dispatch] = useReducer(reducer, initialState);

// Prefer context for global app state over prop drilling
```

### Imports and Exports

#### Import Order
```typescript
// 1. React and external libraries
import React from 'react';
import { useState, useEffect } from 'react';

// 2. Third-party libraries
import axios from 'axios';
import { format } from 'date-fns';

// 3. Internal modules (absolute imports preferred)
import { Button } from '@/components/Button';
import { api } from '@/services/api';
import { formatCurrency } from '@/utils/formatters';

// 4. Relative imports (only when necessary)
import { helper } from './helpers';
import type { User } from './types';
```

#### Export Patterns
```typescript
// Named exports preferred over default exports
export { Button, Input, Modal };

// Barrel exports for cleaner imports
// utils/index.ts
export { formatCurrency } from './currency';
export { formatDate } from './date';
export { validateEmail } from './validation';

// Use default exports sparingly, only for main components
export default function App() { /* ... */ }
```

### Error Handling

#### Try-Catch Blocks
```typescript
// Good: Handle errors appropriately
async function fetchUserData(userId: number): Promise<User | null> {
  try {
    const response = await api.get(`/users/${userId}`);
    return response.data;
  } catch (error) {
    console.error('Failed to fetch user:', error);
    // Log to error reporting service
    reportError(error);
    return null;
  }
}
```

#### Error Boundaries (React)
```tsx
class ErrorBoundary extends React.Component {
  state = { hasError: false };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    reportError(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback />;
    }
    return this.props.children;
  }
}
```

### Testing Guidelines

#### Test Structure
```typescript
// Component test example
describe('Button', () => {
  it('renders with correct text', () => {
    render(<Button onClick={jest.fn()}>Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Click me</Button>);
    fireEvent.click(screen.getByText('Click me'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

#### Test Naming
- Describe what the test verifies: `it('shows loading state during API call')`
- Use descriptive test suite names: `describe('User Authentication')`
- Group related tests logically

#### Mocking
```typescript
// Mock external dependencies
jest.mock('@/services/api');
const mockApi = api as jest.Mocked<typeof api>;

// Mock custom hooks
jest.mock('@/hooks/useAuth');
const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
```

### Performance Best Practices

#### React Optimization
- Use `React.memo()` for expensive components
- Use `useMemo()` for expensive calculations
- Use `useCallback()` for event handlers passed to children
- Implement virtualization for long lists
- Lazy load components with `React.lazy()`

#### Bundle Optimization
- Use dynamic imports for code splitting
- Optimize images and assets
- Remove unused dependencies
- Use tree shaking friendly imports

### Security Guidelines

#### Input Validation
- Validate all user inputs on client and server
- Use parameterized queries for database operations
- Sanitize HTML content
- Implement proper authentication and authorization

#### Sensitive Data
- Never commit secrets, API keys, or credentials
- Use environment variables for configuration
- Implement proper CORS policies
- Use HTTPS in production

### Git Workflow

#### Commit Messages
```
type(scope): description

Types: feat, fix, docs, style, refactor, test, chore

Examples:
feat(auth): add login functionality
fix(ui): resolve button alignment issue
docs(readme): update installation instructions
```

#### Branch Naming
- Feature branches: `feature/add-user-profile`
- Bug fixes: `fix/login-validation`
- Hotfixes: `hotfix/critical-security-patch`

#### Pull Request Guidelines
- Provide clear description of changes
- Reference related issues
- Include screenshots for UI changes
- Ensure all tests pass
- Get code review from at least one team member

### Tooling and Dependencies

#### Package Management
- Use npm for package management
- Keep dependencies up to date
- Audit for security vulnerabilities regularly
- Use exact versions in package.json for reproducible builds

#### Development Tools
- ESLint for code linting
- Prettier for code formatting
- Husky for git hooks
- Commitlint for commit message validation
- Storybook for component development

## Future Improvements Roadmap

### Security & Privacy Enhancements
- **Advanced Credential Management**: Keyring integration, OAuth2 for email access, encrypted .env files
- **Data Encryption**: AES encryption for journal entries, secure memory wiping

### Performance & Scalability
- **Caching & Optimization**: Context caching, model response caching, lazy loading, background processing
- **Keep JSONL Format**: Maintain human-readable JSONL files for journal and telos to allow external program access

### User Experience Improvements
- **Interactive CLI Enhancements**: Auto-completion, progress bars, colored output, interactive editors

### AI & ML Enhancements
- **Advanced AI Features**: Multi-model support, custom fine-tuning, sentiment analysis, predictive suggestions
- **Context Intelligence**: Time-based context weighting, pattern recognition, proactive suggestions

### Email Integration Upgrades
- **Enhanced Processing**: Attachment analysis, calendar extraction, threading, priority scoring
- **Multi-Account Support**: Multiple IMAP accounts, unified inbox, cross-account deduplication

### Analytics & Insights
- **Personal Analytics**: Goal completion trends, productivity patterns, sentiment analysis
- **Reporting System**: Weekly reports, goal summaries, journal insights, email analysis

### Developer Experience
- **Testing Infrastructure**: Unit tests, integration tests, mock servers, CI/CD pipeline
- **Development Tools**: Code quality tools (black, mypy, ruff), API documentation

### Deployment & Distribution
- **Packaging**: PyPI distribution, Docker images, systemd service, desktop app
- **Cloud Integration**: Optional cloud backup/sync, multi-device sync, web access

### Mobile & Cross-Platform
- **Mobile Companion**: React Native app, voice input, push notifications, offline mode
- **Cross-Platform**: Windows/macOS/Linux support, WSL integration

### Integration Ecosystem
- **Third-Party**: Calendar integration, task managers, fitness trackers, social media
- **API Ecosystem**: REST API, webhooks, plugin system, SDK

### Data Management & User Safety
- **Preserve User Data**: Never overwrite or delete user telos (goals/tasks) and journal files during development or version updates
- **Append-Only Philosophy**: All user data files are append-only to prevent data loss
- **Safe Development**: Development workflows must account for existing user data
- **Backup Requirements**: Always backup user data before major changes
- **Migration Safety**: Data migration scripts must be reversible and tested

### Community & Growth
- **Open Source Strategy**: Contribution guidelines, issue templates, regular releases
- **Marketing**: Demo videos, user showcases, partnerships, academic collaborations</content>
<parameter name="filePath">AGENT.md