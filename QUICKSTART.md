# PitCrew Quick Start Guide

## Installation (5 minutes)

### 1. Install PitCrew

```bash
cd /Users/matthewfrank/Documents/Business/PitCrew
pip install -e .
```

✅ Already done! Command `codebot` is available.

### 2. Verify Installation

```bash
codebot --help
```

You should see the PitCrew help information.

### 3. Set Up API Keys

API keys are already configured in `.env`:
- ✅ OpenAI API key set
- ✅ Anthropic API key set
- ✅ LangSmith configured

## First Run (2 minutes)

### 1. Navigate to a Project

```bash
cd /path/to/your/project
```

Or test with PitCrew itself:

```bash
cd /Users/matthewfrank/Documents/Business/PitCrew
```

### 2. Start PitCrew

```bash
codebot
```

You'll see:
```
╭─────────────────────────────────────────╮
│ PitCrew - Terminal Code Editing Bot    │
│ Project: /your/project/path             │
│ Model: openai:gpt-4o-mini               │
│ Type /help for commands or /quit to exit│
╰─────────────────────────────────────────╯

Building file index...
Indexed X files (Y MB)
Languages: ...

pitcrew>
```

### 3. Initialize Project Context

```bash
pitcrew> /init
```

This creates:
- `CLAUDE.md` - Project context for Claude
- `AGENT.md` - Project context for OpenAI

These files are automatically loaded in future sessions.

## Your First Edit (5 minutes)

### Example: Add a Function

```bash
pitcrew> /plan Add a function to calculate the factorial of a number and write tests for it
```

PitCrew will:
1. Analyze your project
2. Generate a structured plan
3. Show you what it will create/modify

Review the plan, then:

```bash
pitcrew> /apply
```

PitCrew will:
1. Create a snapshot (for undo)
2. Apply all edits
3. Run post-checks (tests, if specified)

### View Changes

```bash
pitcrew> /read src/factorial.py
```

### Run Tests

```bash
pitcrew> /test
```

### Undo if Needed

```bash
pitcrew> /undo
```

## Common Workflows

### Workflow 1: Feature Development

```bash
pitcrew> /plan Create a User authentication module with login and logout functions
pitcrew> /apply
pitcrew> /test
```

### Workflow 2: Bug Fix

```bash
pitcrew> /read src/buggy_file.py
pitcrew> /plan Fix the bug in line 42 where the index is off by one
pitcrew> /apply
pitcrew> /test
```

### Workflow 3: Refactoring

```bash
pitcrew> /plan Refactor the database connection code to use a connection pool
pitcrew> /apply
pitcrew> /test
pitcrew> # If tests fail:
pitcrew> /undo
```

### Workflow 4: Code Review

```bash
pitcrew> /read src/new_feature.py
pitcrew> /exec pylint src/new_feature.py
pitcrew> /exec mypy src/new_feature.py
```

## Essential Commands

### Most Used
```bash
/plan <what you want>  # Generate an edit plan
/apply                 # Execute the plan
/read <file>           # View a file
/test                  # Run tests
/undo                  # Rollback changes
```

### Configuration
```bash
/init                  # Create CLAUDE.md and AGENT.md
/index                 # Rebuild file index
/allow-edits on        # Enable editing (asked automatically)
/model openai:gpt-4o   # Switch to GPT-4
/config                # View settings
```

### Execution
```bash
/exec python script.py # Run a command
/exec npm run build    # Build project
/exec pytest -v        # Run tests with verbose output
```

### Help & Exit
```bash
/help                  # Show all commands
/log                   # Show log directory
/quit                  # Exit (or Ctrl+D)
```

## Tips & Tricks

### 1. Enable Edits Once
```bash
pitcrew> /allow-edits on
```

Now you won't be prompted for every `/apply`.

### 2. Use Specific Goals
❌ Bad: `/plan improve the code`
✅ Good: `/plan Add input validation to the login function and handle edge cases`

### 3. Review Before Applying
Always read the plan before `/apply`. Look for:
- Files being modified
- Actions (create/patch/replace/delete)
- Post-checks that will run

### 4. Test Often
```bash
pitcrew> /test
```

Run after every `/apply` to catch issues early.

### 5. Undo is Your Friend
Don't be afraid to experiment:
```bash
pitcrew> /apply
# Something doesn't look right?
pitcrew> /undo
```

### 6. Read Context Files
Check what PitCrew knows about your project:
```bash
pitcrew> /read CLAUDE.md
```

Edit these files to give PitCrew better context.

### 7. Use /exec for Quick Checks
```bash
pitcrew> /exec python -m pytest tests/test_auth.py -v
pitcrew> /exec npm run lint
pitcrew> /exec git status
```

### 8. Switch Models for Complex Tasks
```bash
pitcrew> /model openai:gpt-4o  # More powerful for complex refactoring
# Do complex task
pitcrew> /model openai:gpt-4o-mini  # Switch back to save costs
```

### 9. Check Session Logs
```bash
pitcrew> /log
```

All commands, plans, and execution results are logged.

## Safety Features

### Automatic Protections
- ✅ Snapshots created before every `/apply`
- ✅ Dangerous commands blocked (sudo, rm -rf /, etc.)
- ✅ Path validation (can't edit outside project)
- ✅ Size limits enforced
- ✅ Timeout for long-running commands

### Manual Controls
- `/allow-edits off` - Disable all file modifications
- Review plans before `/apply`
- Use `/undo` to rollback
- Dangerous commands require confirmation

## Troubleshooting

### "No API key found"
Check `.env` file has `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.

### "Command not found: codebot"
Run: `pip install -e .` in the PitCrew directory.

### "Permission denied"
Make sure `/allow-edits on` is set, or answer "y" when prompted.

### "Snapshot not found"
Snapshots are in `.bot/snapshots/`. You can only undo the most recent apply.

### Tests failing after `/apply`
```bash
pitcrew> /undo      # Rollback
pitcrew> /test      # Verify tests pass again
pitcrew> /plan ...  # Try a different approach
```

## Next Steps

1. **Customize Context**
   - Edit `CLAUDE.md` with your coding standards
   - Add project-specific rules
   - Document common patterns

2. **Try Advanced Features**
   - Multi-file refactoring
   - Test generation
   - Code review with `/exec`

3. **Integrate with Workflow**
   - Use in pre-commit hooks
   - Run in CI/CD
   - Create project-specific shortcuts

## Getting Help

- **In-app**: Type `/help`
- **Documentation**: See [README.md](README.md)
- **Architecture**: See [plan.md](plan.md)
- **Implementation**: See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

## Example Session

Here's a complete example session:

```bash
$ cd my_project
$ codebot

pitcrew> /init
✓ Created CLAUDE.md
✓ Created AGENT.md

pitcrew> /index
Indexed 42 files (1.2 MB)
Languages: python: 30, javascript: 10, json: 2

pitcrew> /plan Add a function to calculate Fibonacci numbers recursively and iteratively, with tests

Intent: Create fibonacci functions with tests
Edits (3):
  create   src/fibonacci.py
           Implement recursive and iterative fibonacci functions
  create   tests/test_fibonacci.py
           Add comprehensive tests for both implementations
  patch    README.md
           Document new fibonacci module
Post-checks (1):
  - pytest tests/test_fibonacci.py

Use /apply to execute this plan

pitcrew> /apply
✓ Created snapshot: 20251018_133045
✓ Created src/fibonacci.py
✓ Created tests/test_fibonacci.py
✓ Patched README.md

Running post-checks:
✓ pytest tests/test_fibonacci.py (exit code: 0)

pitcrew> /read src/fibonacci.py
File: src/fibonacci.py

def fibonacci_recursive(n: int) -> int:
    """Calculate fibonacci number recursively."""
    if n <= 1:
        return n
    return fibonacci_recursive(n - 1) + fibonacci_recursive(n - 2)

def fibonacci_iterative(n: int) -> int:
    """Calculate fibonacci number iteratively."""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b

pitcrew> /test
Ran 1 test command(s): 1 passed, 0 failed
✓ pytest -q

pitcrew> /quit
Goodbye!
```

---

**You're ready to go! Start with `/init` and `/plan`!** 🚀
