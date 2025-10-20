# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PitCrew is a terminal-based code editing bot built on LangGraph. It provides an interactive REPL for reading, planning, and applying multi-file edits, executing commands, and maintaining project context via CLAUDE.md/AGENT.md memory files. The system uses a supervisor-node architecture with specialized capability nodes for file operations, planning, execution, and testing.

**Primary use case:** Enable AI-assisted development through natural language commands and slash commands, with safety-first execution policies and explicit approval flows for file modifications.

## Tech Stack

- **Language:** Python 3.x
- **Core Framework:** LangGraph (orchestration), langchain-core
- **LLM Providers:** OpenAI (gpt-4o, gpt-4o-mini); optional Anthropic support planned
- **CLI Framework:** Typer
- **Other Dependencies:** Pydantic (models), Rich (terminal UI), Jinja2 (templates)
- **Entry Point:** `codebot` (via `codebot.cli:main`)

## Architecture

### LangGraph Topology

```
[User/CLI]
   ↓
[Supervisor Node]  ← conversation state, high-level planning
   ├── Tool: FileIndex (walk project, apply ignore rules)
   ├── Tool: ReadWrite (read/write/patch files)
   ├── Tool: Planner (generate multi-file edit plans)
   ├── Tool: Executor (run commands with sandboxing)
   ├── Tool: Tester (discover & run tests: pytest, npm, go test)
   └── Tool: ModelSwitch (switch LLM provider/model)
```

### State Object (BotState)

- `conversation`: list[Message]
- `project_root`: Path
- `active_model`: ModelDescriptor (provider, name, max_tokens)
- `policy`: SafetyPolicy (execution guard config)
- `allow_edits`: bool (session-level approval)
- `index`: FileIndexSnapshot (paths, sizes, hashes, language)
- `context_files`: list[Path] (CLAUDE.md, AGENT.md)
- `run_log_id`: str (session log directory under .pitcrew/)

### Directory Structure

```
pitcrew/
├─ pyproject.toml
├─ README.md
├─ .env.example
├─ pitcrew/
│  ├─ cli.py              # REPL entry point
│  ├─ graph.py            # LangGraph supervisor + node definitions
│  ├─ state.py            # BotState model
│  ├─ llm.py              # LLM provider abstraction
│  ├─ config.py           # Configuration loading
│  ├─ templates/          # CLAUDE.md, AGENT.md Jinja2 templates
│  └─ tools/
│     ├─ file_index.py    # File indexing with ignore rules
│     ├─ read_write.py    # File I/O, patching, snapshots
│     ├─ planner.py       # Multi-file edit plan generation
│     ├─ executor.py      # Command execution with sandbox
│     └─ tester.py        # Test discovery and execution
└─ tests/                 # Unit and integration tests
```

### Key Data Models

**Plan** (Planner output):
- `intent`: str
- `files_to_read`: list[str]
- `edits`: list[EditAction]
- `post_checks`: list[ExecutionAction]

**EditAction**:
- `path`, `action` (create|patch|replace|delete), `justification`
- `patch_unified` or `content` depending on action

**ExecutionAction**:
- `command`, `cwd`

## File & Folder Conventions

### Context Files
- **CLAUDE.md** (primary project rules, workflows, conventions)
- **CLAUDE.local.md** (private, machine-local overrides)
- **AGENT.md** (OpenAI-friendly mirror)
- Supports nested CLAUDE.md in subdirectories for scoped instructions

### Ignore Rules
- `.pitcrew/pitcrewignore` (first-class, project-specific)
- `.gitignore` (respected)
- Built-in binary and size guards

### Internal Data (.pitcrew/)
- `runs/<timestamp>/`: transcripts, plans, patches, exec logs
- `snapshots/`: pre-write backups for `/undo`
- `index.json`: file index summary
- `config.json`: resolved configuration
- `pitcrewignore`: custom ignore patterns

## Commands

### Development
- **Install (dev mode):** `pip install -e .`
- **Run:** `codebot` (in project root) or `codebot /path/to/project`
- **Test:** `pytest -q` (assumes pytest installed)
- **Lint:** Define in project config or use standard Python tooling

### REPL Slash Commands
- `/init` — create CLAUDE.md/AGENT.md with template
- `/plan <goal>` — produce structured multi-file edit plan
- `/apply` — execute last plan (requires approval or `allow_edits`)
- `/read <path|glob>` — show file contents
- `/write <path>` — edit file (or accept patch)
- `/exec <cmd>` — execute command (sandboxed by default)
- `/test` — auto-detect and run tests
- `/model` — show/set active LLM model
- `/allow-edits on|off` — toggle session write permission
- `/index` — rebuild file index
- `/config` — show effective configuration
- `/undo` — revert last batch of edits
- `/log` — show session log path
- `/quit` — exit REPL

### Natural Language
Users can describe tasks conversationally. The supervisor will read files, propose a plan, prompt to `/apply`, and optionally `/test`.

## Configuration

### Environment Variables (.env)
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY` (optional, future)
- `CODEBOT_DEFAULT_MODEL` (default: `openai:gpt-4o-mini`)
- `CODEBOT_EXEC_NET` (deny|allow, default: deny)
- `CODEBOT_EXEC_TIMEOUT` (seconds, default: 45)
- `CODEBOT_MAX_READ_MB` (default: 8)
- `CODEBOT_MAX_WRITE_MB` (default: 2)

### Custom Commands (.pitcrew/config.json)
Override default test/build/lint commands:
```json
{
  "commands": {
    "build": "make build",
    "test": "pytest -q",
    "lint": "ruff check ."
  }
}
```

## Safety & Execution

### Sandbox Policy (Default)
- Runs commands via `subprocess.Popen` in project root
- Pruned environment (safe PATH, PYTHONPATH only)
- **No network by default**
- CPU/wall-clock timeouts, output truncation
- Denies dangerous patterns: `sudo`, `rm -rf /`, fork bombs, etc.
- Use `/exec --no-sandbox` to bypass (requires explicit confirmation)

### Approval Flow
- First write in session prompts: "Allow edits for this session? (y/N)"
- If approved: `allow_edits=True`; user can toggle via `/allow-edits off`

## Workflow: Plan → Apply

1. User requests feature or refactor (natural language or `/plan <goal>`)
2. Supervisor reads relevant files, generates structured `Plan`
3. REPL displays concise diff summary, asks to `/apply`
4. On `/apply`:
   - Snapshot current state → `.pitcrew/snapshots/`
   - Apply edits atomically
   - Optionally run `post_checks` (tests, linters)
5. If tests fail or user wants to revert: `/undo`

## Test Discovery (v1)
Auto-detection logic:
- If `pytest.ini` or `tests/` exists → `pytest -q`
- If `package.json` with `"test"` script → `npm test --silent`
- If `go.mod` exists → `go test ./...`
- Override via `.pitcrew/config.json` commands

## Logging & Undo
- **Logs:** `.pitcrew/runs/<timestamp>/transcript.ndjson`, `plan.json`, `diffs/`, `exec/`
- **Undo:** Restores from `.pitcrew/snapshots/<id>/` (last batch of edits)

## Non-Goals (v1)
- No Git integration (relies on snapshots/undo)
- No Docker or cross-OS testing
- No embeddings/vector store
- No multi-repo orchestration
