# PitCrew Implementation Plan

## Overview
Full implementation plan for PitCrew - a terminal-based code editing bot using LangGraph.

## System Architecture

### Phase 1: Foundation (Core Infrastructure)
**Goal:** Set up project structure, configuration, and base utilities

#### 1.1 Project Setup
- [x] Create `pyproject.toml` with all dependencies
  - LangGraph (latest), LangChain Core
  - OpenAI SDK, Anthropic SDK
  - Pydantic v2, Typer, Rich
  - unidiff (for robust patch handling)
  - pytest, pytest-asyncio (testing)
- [x] Create directory structure:
  ```
  pitcrew/
  ├── pyproject.toml
  ├── README.md
  ├── CLAUDE.md
  ├── plan.md
  ├── .env
  ├── .env.example
  ├── .gitignore
  ├── .codebotignore
  ├── pitcrew/
  │   ├── __init__.py
  │   ├── cli.py              # Entry point, REPL
  │   ├── graph.py            # LangGraph setup
  │   ├── state.py            # BotState model
  │   ├── config.py           # Config loading
  │   ├── llm.py              # LLM abstraction
  │   ├── constants.py        # Constants, defaults
  │   ├── templates/
  │   │   ├── AGENT.md.j2
  │   │   └── CLAUDE.md.j2
  │   ├── tools/
  │   │   ├── __init__.py
  │   │   ├── file_index.py   # File indexing
  │   │   ├── read_write.py   # File I/O, snapshots
  │   │   ├── planner.py      # Edit plan generation
  │   │   ├── executor.py     # Command execution
  │   │   └── tester.py       # Test discovery/running
  │   └── utils/
  │       ├── __init__.py
  │       ├── diffs.py        # Diff/patch utilities
  │       ├── ignore.py       # Ignore rules parser
  │       └── logging.py      # Session logging
  └── tests/
      ├── __init__.py
      ├── conftest.py         # Pytest fixtures
      ├── test_index.py
      ├── test_read_write.py
      ├── test_patching.py
      ├── test_executor.py
      ├── test_planner.py
      ├── test_tester.py
      ├── test_integration.py
      └── test_e2e.py
  ```

#### 1.2 Core Models & Configuration
**Files:** `state.py`, `config.py`, `constants.py`

**state.py:**
```python
class BotState(TypedDict):
    conversation: list[dict]
    project_root: str
    active_model: str
    allow_edits: bool
    index: Optional[dict]  # FileIndexSnapshot
    last_plan: Optional[dict]
    run_log_id: Optional[str]
    policy: dict
    context_files: list[str]
```

**config.py:**
- Load from .env (python-dotenv)
- Merge with .bot/config.json if exists
- Provide: OPENAI_API_KEY, ANTHROPIC_API_KEY, defaults for timeouts, limits
- Config dataclass with validation

**constants.py:**
- Default model: "openai:gpt-4o-mini"
- Default timeouts, size limits
- Dangerous command patterns (regex list)
- Template paths

#### 1.3 Utilities
**Files:** `utils/ignore.py`, `utils/diffs.py`, `utils/logging.py`

**ignore.py:**
- Parse .gitignore and .codebotignore using pathspec library
- Provide: `should_ignore(path: Path) -> bool`
- Built-in ignores: .git/, node_modules/, __pycache__, *.pyc, .bot/

**diffs.py:**
- Use `unidiff` library
- `create_patch(original: str, modified: str, filename: str) -> str`
- `apply_patch(content: str, patch: str) -> str`
- Error handling for patch failures

**logging.py:**
- Session logger: writes to `.bot/runs/<timestamp>/transcript.ndjson`
- Log message format: `{"ts": ..., "role": ..., "content": ..., "tool_calls": ...}`
- `save_plan(plan: dict)`, `save_exec_result(cmd: str, result: dict)`

### Phase 2: Tools Layer (LangGraph Capabilities)

#### 2.1 FileIndex Tool
**File:** `tools/file_index.py`

**Class:** `FileIndex`
- `__init__(project_root: Path, ignore_rules: IgnoreRules)`
- `build() -> FileIndexSnapshot`
  - Walk directory tree
  - Skip ignored paths
  - Collect: path, size, mtime, hash (MD5), language (by extension)
  - Store as dict for serialization
- `summarize() -> str`
  - Return human-readable summary: "X files, Y MB, languages: ..."
- `save_to_disk()` -> write to `.bot/index.json`
- `load_from_disk()` -> restore if exists and fresh

**FileIndexSnapshot:** dict with structure:
```python
{
  "files": [
    {"path": "src/main.py", "size": 1234, "mtime": ..., "hash": "...", "lang": "python"},
    ...
  ],
  "summary": {"total_files": 42, "total_size": 123456, "languages": {"python": 20, ...}}
}
```

#### 2.2 ReadWrite Tool
**File:** `tools/read_write.py`

**Class:** `ReadWrite`
- `__init__(project_root: Path, max_read_mb: int, max_write_mb: int)`
- `read(path: str, mode: str = "auto") -> str`
  - Check size limits
  - Handle text vs binary detection
  - Return content or error
- `write(path: str, content: str) -> None`
  - Validate path is within project_root
  - Check size limits
  - Create parent dirs if needed
  - Write atomically (temp file + rename)
- `patch(path: str, unified_diff: str) -> PatchResult`
  - Read current content
  - Apply patch using `utils/diffs.py`
  - Write back if successful
  - Return success/failure with details
- `create_snapshot() -> str`
  - Generate snapshot ID (timestamp)
  - Copy current state of files to `.bot/snapshots/<id>/`
  - Return snapshot ID
- `restore_snapshot(snapshot_id: str) -> None`
  - Copy files back from snapshot directory
  - Overwrite current state

**PatchResult:** dataclass with `success: bool`, `error: Optional[str]`

#### 2.3 LLM Abstraction
**File:** `llm.py`

**Class:** `ModelDescriptor`
```python
@dataclass
class ModelDescriptor:
    provider: Literal["openai", "anthropic"]
    name: str
    max_output_tokens: int
    temperature: float = 0.7
```

**Class:** `LLM`
- `__init__(descriptor: ModelDescriptor, api_key: str)`
- `complete(messages: list[dict], tools: Optional[list[dict]] = None, temperature: Optional[float] = None) -> dict`
  - Route to OpenAI or Anthropic client
  - Handle tool calling format differences
  - Return normalized response
- `parse_model_string(model_str: str) -> ModelDescriptor`
  - Parse "openai:gpt-4o" -> ModelDescriptor
  - Validate model exists

**Supported Models:**
- openai:gpt-4o (max_tokens: 4096)
- openai:gpt-4o-mini (max_tokens: 4096)
- anthropic:claude-3-5-sonnet-20241022 (max_tokens: 8192)

#### 2.4 Planner Tool
**File:** `tools/planner.py`

**Class:** `Planner`
- `__init__(llm: LLM, project_root: Path)`
- `make_plan(goal: str, index: FileIndexSnapshot, context_docs: list[str]) -> Plan`

**Planning Strategy (Hybrid):**
1. **Rule-based pre-processing:**
   - Analyze goal for keywords: "create class", "refactor", "add function", etc.
   - Infer likely files from index based on language, naming patterns
   - Apply project conventions from CLAUDE.md/AGENT.md

2. **LLM-powered plan generation:**
   - Construct prompt with:
     - User goal
     - File index summary
     - Context from CLAUDE.md/AGENT.md
     - Conventions: "prefer patches over full rewrites", "organize into classes"
   - Request structured JSON response (use tool calling or JSON mode)
   - Parse into Plan object

3. **Post-processing:**
   - Validate all file paths exist (or are marked for creation)
   - Check patch syntax
   - Ensure post_checks are valid commands

**Plan Model:**
```python
class EditAction(BaseModel):
    path: str
    action: Literal["create", "patch", "replace", "delete"]
    justification: str
    patch_unified: Optional[str] = None
    content: Optional[str] = None

class ExecutionAction(BaseModel):
    command: str
    cwd: Optional[str] = None

class Plan(BaseModel):
    intent: str
    files_to_read: list[str]
    edits: list[EditAction]
    post_checks: list[ExecutionAction]
```

#### 2.5 Executor Tool
**File:** `tools/executor.py`

**Class:** `Executor`
- `__init__(project_root: Path, policy: dict)`
- `run(command: str, timeout: int = 45, sandbox: bool = True) -> ExecResult`
  - Check if command is dangerous
  - If dangerous and not confirmed, return error
  - Execute via subprocess.Popen
  - Capture stdout/stderr
  - Apply timeout
  - Return result
- `is_dangerous(command: str) -> tuple[bool, str]`
  - Check against patterns: sudo, rm -rf /, curl | sh, etc.
  - Return (is_dangerous, reason)

**Sandbox Implementation (Simple):**
- Run in project_root as cwd
- Prune environment variables (keep PATH, PYTHONPATH, HOME)
- Set resource limits: CPU time (via resource module on Unix)
- Wall-clock timeout via subprocess timeout
- No network blocking initially (future: use network namespace on Linux)

**Dangerous Patterns:**
```python
DANGEROUS_PATTERNS = [
    r'\bsudo\b',
    r'\brm\s+-rf\s+/',
    r':\(\)\{.*\|.*\&.*\}',  # fork bomb
    r'curl.*\|.*sh',
    r'wget.*\|.*sh',
    r'\bchmod\s+777',
]
```

**ExecResult:**
```python
@dataclass
class ExecResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    command: str
```

#### 2.6 Tester Tool
**File:** `tools/tester.py`

**Class:** `Tester`
- `__init__(project_root: Path, executor: Executor, config: dict)`
- `detect() -> list[str]`
  - Check for pytest.ini, tests/ -> return `["pytest", "-q"]`
  - Check for package.json with test script -> return `["npm", "test", "--silent"]`
  - Check for go.mod -> return `["go", "test", "./..."]`
  - Check for .bot/config.json override -> return custom command
  - Return empty list if nothing found
- `run_all() -> list[ExecResult]`
  - Detect test commands
  - Execute each via Executor
  - Return results

**Test Detection Priority:**
1. `.bot/config.json` "commands.test" (highest)
2. Language-specific patterns
3. Empty (no tests found)

### Phase 3: LangGraph Orchestration

#### 3.1 Graph Construction
**File:** `graph.py`

**State:** Use `BotState` from `state.py`

**Nodes:**
1. **supervisor** - main orchestration node
   - Parses user input (slash command or natural language)
   - Routes to appropriate tool
   - Updates conversation state
   - Returns response

**Tools (for LangGraph tool calling):**
- Define each tool (FileIndex, ReadWrite, Planner, Executor, Tester) as LangGraph tools
- Tools return structured results that supervisor can use

**Graph Structure:**
```python
def build_graph() -> CompiledGraph:
    workflow = StateGraph(BotState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.set_entry_point("supervisor")
    workflow.set_finish_point("supervisor")

    # Tools registered separately for supervisor to call

    return workflow.compile()
```

**Supervisor Logic:**
- If input starts with `/` -> parse slash command
  - `/init` -> use ReadWrite to create CLAUDE.md/AGENT.md from templates
  - `/plan <goal>` -> call Planner, store in state.last_plan
  - `/apply` -> execute state.last_plan using ReadWrite
  - `/read <path>` -> call ReadWrite.read()
  - `/exec <cmd>` -> call Executor.run()
  - `/test` -> call Tester.run_all()
  - `/model` -> update state.active_model
  - `/allow-edits on|off` -> update state.allow_edits
  - `/index` -> call FileIndex.build()
  - `/undo` -> call ReadWrite.restore_snapshot()
  - `/config` -> print current config
  - `/log` -> print log path
  - `/quit` -> exit
- Else -> natural language
  - Call LLM with conversation history + available tools
  - LLM decides which tools to call
  - Execute tool calls
  - Return response

#### 3.2 Tool Registration
- Each tool class has a `to_langchain_tool()` method
- Returns LangChain Tool object with:
  - name, description, input schema
  - run function

### Phase 4: CLI & REPL

#### 4.1 CLI Entry Point
**File:** `cli.py`

**Main function:**
```python
import typer
from rich.console import Console

app = typer.Typer()

@app.command()
def main(
    path: Optional[str] = typer.Argument(None, help="Project path"),
    model: Optional[str] = typer.Option(None, help="Model to use"),
):
    """PitCrew - Terminal Code Editing Bot"""
    project_root = Path(path) if path else Path.cwd()

    # Load config
    # Initialize tools
    # Build graph
    # Start REPL
```

**REPL:**
- Use Rich for pretty output
- Prompt: `pitcrew> `
- Read user input
- Pass to graph
- Display response
- Handle Ctrl+C gracefully
- Show help on empty input or /help

**Rich Formatting:**
- Use panels for plan summaries
- Use syntax highlighting for code/diffs
- Use progress bars for long operations
- Use tables for file lists

#### 4.2 Session Management
- On startup:
  - Create `.bot/runs/<timestamp>/` directory
  - Initialize transcript logger
  - Load context files (CLAUDE.md, AGENT.md)
  - Build or load file index
- On shutdown:
  - Flush logs
  - Save final state

### Phase 5: Templates

#### 5.1 CLAUDE.md Template
**File:** `pitcrew/templates/CLAUDE.md.j2`

**Sections:**
1. Project Overview (placeholder)
2. Tech Stack & Conventions (detect from project)
3. How to Run (placeholder with common patterns)
4. How to Test (placeholder)
5. Architecture Map (generated from index)
6. Editing Rules (general best practices)
7. Non-negotiables (security reminders)
8. Task Guide (how to use /plan, /apply, /test)

**Template Variables:**
- `project_name`: from directory name
- `languages`: from index
- `test_framework`: from tester detection
- `file_tree`: simplified tree view

#### 5.2 AGENT.md Template
**File:** `pitcrew/templates/AGENT.md.j2`

**Content:** Similar to CLAUDE.md but optimized for OpenAI models
- More structured sections
- Explicit formatting rules
- Tool usage examples

### Phase 6: Testing

#### 6.1 Unit Tests
**Files:** `tests/test_*.py`

**test_index.py:**
- Test FileIndex.build() respects ignore rules
- Test language detection
- Test size limits
- Test hash generation

**test_read_write.py:**
- Test read with size limits
- Test write creates parent dirs
- Test snapshot/restore functionality
- Test path validation (prevent directory traversal)

**test_patching.py:**
- Test create_patch generates valid unified diff
- Test apply_patch with various scenarios
- Test patch failure handling
- Test CRLF/LF handling

**test_executor.py:**
- Test is_dangerous() with patterns
- Test command execution with timeout
- Test stdout/stderr capture
- Test resource limits (if possible)

**test_planner.py:**
- Test rule-based analysis
- Test LLM plan generation (mock LLM)
- Test plan validation
- Test malformed plan handling

**test_tester.py:**
- Test auto-detection for pytest
- Test auto-detection for npm
- Test auto-detection for go test
- Test custom command from config

#### 6.2 Integration Tests
**File:** `tests/test_integration.py`

**Test scenarios:**
- Full /init flow: creates CLAUDE.md and AGENT.md
- /plan + /apply: modifies multiple files
- /exec + /test: runs commands and tests
- /undo: restores previous state
- Error handling: invalid commands, permission errors

#### 6.3 E2E Test
**File:** `tests/test_e2e.py`

**Test scenario:**
1. Create temporary project (Python lib with simple function)
2. Start PitCrew session
3. Ask: "Add a function to calculate factorial and add tests"
4. Verify:
   - Plan generated
   - Files created/modified
   - Tests pass
   - Logs created

### Phase 7: Polish & Documentation

#### 7.1 Error Handling
- Graceful failures for all tools
- Clear error messages
- Recovery suggestions
- Log all errors

#### 7.2 Documentation
- README.md: updated with install instructions
- .env.example: template for configuration
- Inline docstrings: all public functions
- Type hints: full coverage

#### 7.3 .gitignore
- Add .bot/ (logs, snapshots)
- Add .env
- Standard Python ignores

## Implementation Order

### Sprint 1: Foundation
1. Project setup (pyproject.toml, structure)
2. Core models (state.py, config.py, constants.py)
3. Utilities (ignore.py, diffs.py, logging.py)
4. Unit tests for utilities

### Sprint 2: Tools
5. FileIndex + tests
6. ReadWrite + tests
7. LLM abstraction + tests
8. Planner + tests (mocked LLM initially)

### Sprint 3: Execution
9. Executor + tests
10. Tester + tests
11. Integration tests for tools

### Sprint 4: Orchestration
12. LangGraph setup
13. Supervisor node
14. Tool registration
15. Integration tests for graph

### Sprint 5: CLI
16. CLI entry point
17. REPL implementation
18. Rich formatting
19. Session management

### Sprint 6: Templates & E2E
20. Jinja2 templates
21. /init implementation
22. E2E test
23. Full system test

### Sprint 7: Polish
24. Error handling improvements
25. Documentation
26. Final testing
27. Bug fixes

## Success Criteria

- [ ] Can start REPL with `codebot`
- [ ] /init creates valid CLAUDE.md and AGENT.md
- [ ] /plan generates intelligent multi-file plans
- [ ] /apply executes plans and modifies files
- [ ] /undo restores previous state
- [ ] /exec runs commands safely
- [ ] /test auto-detects and runs tests
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] E2E test passes
- [ ] No security vulnerabilities
- [ ] Clean error messages
- [ ] Logs created properly

## Notes

- Use Pydantic v2 for all models
- Use Python 3.11+ features (match/case, improved type hints)
- Follow PEP 8 style
- Keep functions small and focused
- Prioritize clarity over cleverness
- Document all non-obvious behavior
- Test edge cases thoroughly
