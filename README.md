# PitCrew

**A terminal-based AI code editing bot powered by LangGraph**

PitCrew is an interactive REPL that helps you plan, edit, and test code using Large Language Models. It provides intelligent multi-file editing with safety checks, snapshots for undo, and integrated testing.

## Features

- 🤖 **AI-Powered Planning**: Generate intelligent multi-file edit plans using GPT-4 or Claude
- 📝 **Smart File Operations**: Read, write, patch files with safety checks and path validation
- 🔄 **Snapshot & Undo**: Automatic snapshots before changes with easy rollback
- 🧪 **Integrated Testing**: Auto-detect and run tests (pytest, npm, go test, etc.)
- 🛡️ **Sandboxed Execution**: Run commands with resource limits and safety checks
- 📊 **File Indexing**: Fast project-wide file indexing with gitignore support
- 🎯 **Context Management**: Auto-load CLAUDE.md and AGENT.md for project-specific rules
- 🔀 **Model Switching**: Switch between OpenAI and Anthropic models on the fly

## Installation

### Prerequisites

- Python 3.11 or later
- OpenAI API key (required)
- Anthropic API key (optional)

### Install from Source

```bash
# Clone the repository
git clone https://github.com/yourusername/pitcrew.git
cd pitcrew

# Install in development mode
pip install -e .

# Or install dependencies separately
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in your project root:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Configuration (optional, defaults shown)
CODEBOT_DEFAULT_MODEL=openai:gpt-4o-mini
CODEBOT_EXEC_TIMEOUT=45
CODEBOT_MAX_READ_MB=8
CODEBOT_MAX_WRITE_MB=2
```

Or set environment variables directly.

## Quick Start

### Start PitCrew

```bash
# In current directory
codebot

# Or specify a project path
codebot /path/to/project

# With specific model
codebot --model openai:gpt-4o
```

### Basic Workflow

```bash
pitcrew> /init                    # Create CLAUDE.md and AGENT.md
pitcrew> /index                   # Build file index
pitcrew> /plan Add a calculator class with tests
pitcrew> /apply                   # Apply the generated plan
pitcrew> /test                    # Run tests
pitcrew> /undo                    # Rollback if needed
```

## Commands

### Project Setup
- `/init` - Create CLAUDE.md and AGENT.md templates
- `/index` - Build or rebuild file index

### Planning & Editing
- `/plan <goal>` - Generate a structured edit plan
- `/apply` - Execute the last generated plan
- `/read <path>` - Read and display a file
- `/undo` - Revert the last applied changes

### Execution
- `/exec <command>` - Execute a command (with safety checks)
- `/test` - Auto-detect and run project tests

### Configuration
- `/allow-edits on|off` - Toggle file editing permissions
- `/model [name]` - Show current model or switch to a new one
- `/config` - Display current configuration
- `/log` - Show session log path

### Help & Exit
- `/help` - Show available commands
- `/quit` - Exit PitCrew

## Supported Models

### OpenAI
- `openai:gpt-4o` - Latest GPT-4 Omni
- `openai:gpt-4o-mini` - Faster, cheaper GPT-4 variant (default)

### Anthropic
- `anthropic:claude-3-5-sonnet-20241022` - Claude 3.5 Sonnet

Switch models anytime with `/model <model_name>`.

## Examples

### Example 1: Create a New Feature

```bash
pitcrew> /plan Create a User class with name and email fields, add validation, and write tests

# PitCrew generates a plan showing:
# - New file: src/user.py with User class
# - New file: tests/test_user.py with test cases
# - Post-check: Run pytest

pitcrew> /apply
✓ Created src/user.py
✓ Created tests/test_user.py

Running post-checks:
✓ pytest -q

pitcrew> /read src/user.py
# View the generated code
```

### Example 2: Refactor Code

```bash
pitcrew> /plan Refactor the authentication module to use environment variables instead of hardcoded credentials

# Review plan
pitcrew> /apply
# Changes applied

pitcrew> /test
# Verify everything still works

# If something breaks:
pitcrew> /undo
# Rollback to previous state
```

### Example 3: Run Custom Commands

```bash
pitcrew> /exec python script.py --verbose
# Command: python script.py --verbose
# Exit code: 0
# Stdout:
# Processing complete!

pitcrew> /exec npm run build
# Builds your project
```

## Architecture

PitCrew uses LangGraph to orchestrate a set of specialized tools:

- **FileIndex**: Walks project tree, respects .gitignore/.codebotignore
- **ReadWrite**: File I/O with snapshots for undo functionality
- **Planner**: Hybrid rule-based + LLM plan generation
- **Executor**: Sandboxed command execution with safety checks
- **Tester**: Auto-detects test frameworks and runs tests

See [plan.md](plan.md) for detailed architecture documentation.

## Project Context Files

PitCrew automatically loads context from special markdown files:

### CLAUDE.md
Project-wide conventions, architecture, and guidelines. Created with `/init`.

### AGENT.md
Alternative format optimized for OpenAI models. Also created with `/init`.

### CLAUDE.local.md (optional)
Machine-local context (not committed to git). Useful for local paths or preferences.

These files are loaded at session start and provided to the LLM when generating plans.

## Safety Features

### File Operations
- Path validation (prevents directory traversal)
- Size limits (configurable via environment)
- Automatic snapshots before batch edits
- Atomic writes (temp file + rename)

### Command Execution
- Dangerous command detection (sudo, rm -rf, curl | sh, etc.)
- Resource limits (CPU time, memory, processes)
- Timeout enforcement
- Environment variable pruning

### Edit Permissions
- Explicit approval on first edit
- Session-level `/allow-edits` toggle
- Snapshot before every apply

## Development

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=pitcrew --cov-report=term-missing

# Run specific test file
pytest tests/test_file_index.py -v
```

### Project Structure

```
pitcrew/
├── pitcrew/
│   ├── cli.py              # REPL and command handling
│   ├── graph.py            # LangGraph orchestration
│   ├── state.py            # State management
│   ├── config.py           # Configuration
│   ├── llm.py              # LLM abstraction layer
│   ├── tools/              # Specialized tools
│   │   ├── file_index.py
│   │   ├── read_write.py
│   │   ├── planner.py
│   │   ├── executor.py
│   │   └── tester.py
│   ├── utils/              # Utilities
│   │   ├── ignore.py
│   │   ├── diffs.py
│   │   └── logging.py
│   └── templates/          # Jinja2 templates
│       ├── CLAUDE.md.j2
│       └── AGENT.md.j2
├── tests/                  # Test suite
├── plan.md                 # Detailed implementation plan
├── CLAUDE.md               # PitCrew's own context
└── README.md               # This file
```

## Logging

All sessions are logged to `.bot/runs/<timestamp>/`:

- `transcript.ndjson` - Conversation messages
- `plan.json` - Generated plans
- `diffs/` - File diffs from edits
- `exec/` - Command execution results

Access log path with `/log` command.

## Roadmap

### v0.1.0 (Current)
- ✅ Core REPL with slash commands
- ✅ File indexing and ignore rules
- ✅ LLM-powered planning
- ✅ File operations with snapshots
- ✅ Command execution with sandboxing
- ✅ Test auto-detection
- ✅ Multiple LLM provider support

### Future
- Natural language mode (conversational interface)
- Git integration (branch, commit, PR creation)
- Vector search for large codebases
- Interactive patch review
- Multi-repo support
- Plugin system

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Credits

Built with:
- [LangGraph](https://github.com/langchain-ai/langgraph) - LLM application orchestration
- [LangChain](https://github.com/langchain-ai/langchain) - LLM framework
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation

---

**Need help?** Run `/help` in the REPL or check [plan.md](plan.md) for detailed documentation.
