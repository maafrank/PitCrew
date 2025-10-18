# PitCrew

**AI-powered terminal code editor with natural language interface**

PitCrew is an interactive terminal application that lets you edit code using natural conversation. Just describe what you want - no need to learn commands. Built with LangGraph, it provides intelligent multi-file editing, testing, and execution.

## ✨ Key Features

- 💬 **Natural Language Interface**: Chat naturally - "Add error handling to login" or "Tell me about this project"
- 🤖 **AI-Powered Planning**: Intelligent multi-file edit plans using GPT-4 or Claude
- ⚡ **Autonomous Execution**: Automatically plans → applies → tests your changes
- 📝 **Smart File Operations**: Read, write, patch with safety checks
- 🔄 **Snapshot & Undo**: Automatic backups before changes
- 🧪 **Test Integration**: Auto-detect and run pytest, npm test, go test, etc.
- 🛡️ **Sandboxed Execution**: Safe command execution with resource limits
- 🎯 **Project Context**: Learns from CLAUDE.md and AGENT.md files
- 🔀 **Multi-Model**: Switch between OpenAI and Anthropic models instantly

## 🚀 Quick Start

### Installation

```bash
# Install from source
cd pitcrew
pip install -e .
```

### Configuration

Create `.env` file:

```bash
# At least one API key required
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here

# Optional settings
PITCREW_DEFAULT_MODEL=anthropic:claude-3-5-sonnet-20241022
PITCREW_EXEC_TIMEOUT=45
```

### Run

```bash
# Start in current directory
pitcrew

# Or specify project
pitcrew /path/to/project
```

## 💬 Usage Examples

### Natural Language (Recommended)

```
pitcrew> Tell me about this project
🤖 This is a Python project with 42 files...

pitcrew> Add input validation to the login function with tests
🤖 Planning...
📋 Plan: Create validators.py, add tests, update login.py
Apply? (y/N): y
✅ Done! All tests pass.

pitcrew> What's in the config file?
🤖 [Shows and explains config.py]

pitcrew> Run the tests
🧪 Running tests...
✓ 19 passed in 1.2s
```

### Slash Commands (Alternative)

```
pitcrew> /init                          # Create CLAUDE.md
pitcrew> /plan Add feature X            # Generate plan
pitcrew> /apply                         # Execute plan
pitcrew> /read src/main.py              # View file
pitcrew> /test                          # Run tests
pitcrew> /undo                          # Rollback changes
pitcrew> /model openai:gpt-4o           # Switch model
```

## 📋 Available Commands

### Project Setup
- `/init` - Create CLAUDE.md and AGENT.md templates
- `/index` - Build/rebuild file index

### Code Operations
- `/plan <goal>` - Generate edit plan
- `/apply` - Execute last plan
- `/read <path>` - Display file
- `/undo` - Restore last snapshot

### Execution
- `/exec <command>` - Run command (sandboxed)
- `/test` - Auto-detect and run tests

### Settings
- `/allow-edits on|off` - Toggle edit permissions
- `/model [name]` - Show/switch LLM model
- `/config` - Show configuration

### Help
- `/help` - Show commands
- `/quit` - Exit

## 🤖 Supported Models

### Anthropic (Recommended)
- `anthropic:claude-3-5-sonnet-20241022` - Best for structured tasks

### OpenAI
- `openai:gpt-4o` - Most capable
- `openai:gpt-4o-mini` - Faster, cheaper

Switch anytime: `/model <name>` or set `PITCREW_DEFAULT_MODEL` in `.env`

## 🔒 Safety Features

- ✅ Path validation (prevents directory traversal)
- ✅ Dangerous command detection (blocks sudo, rm -rf, etc.)
- ✅ Resource limits (CPU, memory, processes)
- ✅ Automatic snapshots before edits
- ✅ Explicit approval required for changes
- ✅ Size limits on read/write operations

## 📁 Project Structure

```
pitcrew/
├── pitcrew/
│   ├── cli.py              # REPL + natural language handling
│   ├── graph.py            # LangGraph orchestration
│   ├── conversation.py     # Context management
│   ├── intent.py           # Intent detection
│   ├── llm.py              # LLM abstraction (OpenAI + Anthropic)
│   ├── handlers/           # Query, autonomous execution
│   ├── tools/              # FileIndex, ReadWrite, Planner, Executor, Tester
│   ├── utils/              # Ignore rules, diffs, logging
│   └── templates/          # CLAUDE.md, AGENT.md templates
├── tests/                  # 19 unit tests (100% passing)
├── README.md               # This file
├── QUICKSTART.md           # Detailed getting started guide
├── CLAUDE.md               # Project context for PitCrew itself
└── plan.md                 # Detailed architecture documentation
```

## 🎯 How It Works

1. **Intent Detection**: LLM determines what you want (query, plan, read, execute, test)
2. **Context Gathering**: Loads project info, CLAUDE.md, conversation history
3. **Execution**: Routes to appropriate handler (query, autonomous, etc.)
4. **Response**: Clear, actionable feedback with next steps

### Example Flow

```
User: "Add error handling to login"
  ↓
Intent Detector: action=plan, confidence=0.9
  ↓
Autonomous Handler:
  1. Generate plan (create error.py, update login.py, add tests)
  2. Ask for approval
  3. Apply changes with snapshot
  4. Run tests
  5. Report results
  ↓
"✅ Done! 3 files changed, all tests pass."
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=pitcrew

# Run specific test
pytest tests/test_executor.py -v
```

**Test Status:** 19/19 passing ✅

## 📚 Documentation

- **README.md** (this file) - Overview and quick start
- **QUICKSTART.md** - Detailed tutorial with examples
- **CLAUDE.md** - Project context (auto-loaded by PitCrew)
- **plan.md** - Complete architecture and implementation details

## 🔧 Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Format code
black pitcrew/

# Lint
ruff check pitcrew/

# Type check
mypy pitcrew/
```

## 🗺️ Roadmap

### Current (v0.1.0)
- ✅ Natural language interface
- ✅ Multi-file planning and editing
- ✅ Test integration
- ✅ Snapshot/undo
- ✅ OpenAI + Anthropic support

### Future
- 🔜 Streaming LLM responses
- 🔜 File finder (fuzzy search)
- 🔜 Git integration (commit, branch, PR)
- 🔜 Multi-turn plan refinement
- 🔜 VS Code extension
- 🔜 Voice input
- 🔜 RAG for large codebases

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Credits

Built with:
- [LangGraph](https://github.com/langchain-ai/langgraph) - LLM orchestration
- [LangChain](https://github.com/langchain-ai/langchain) - LLM framework
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation

## 💡 Tips

- **First time?** Run `/init` to create context files
- **Large changes?** Review the plan before `/apply`
- **Something broke?** Use `/undo` to rollback
- **Need help?** Just ask naturally or type `/help`
- **Pro tip:** Edit CLAUDE.md with your coding standards for better results

---

**Questions?** See [QUICKSTART.md](QUICKSTART.md) for detailed examples

**Status:** Production ready • Actively maintained • All tests passing ✅
