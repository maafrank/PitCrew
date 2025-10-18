# PitCrew

Product Spec — Terminal Code Editing Bot (LangGraph)

Goals
	•	Terminal-based chatbot that can:
	1.	read & reason over all files under the selected project root (with ignore rules)
	2.	create and maintain a CLAUDE.md/AGENT.md project memory file for persistent context
	3.	plan and apply edits across multiple files
	4.	execute files/commands to test changes (with opt-in safety checks)
	5.	switch models via /model
	•	Installable Python package (pip install -e . during development).
	•	Works on macOS and Linux.
	•	Primary models: OpenAI gpt-4o and gpt-4o-mini; optional Anthropic later.

Key Behavior: CLAUDE.md
	•	Claude Code treats CLAUDE.md (and CLAUDE.local.md) as a special context file automatically pulled into the conversation at session start; it’s ideal for project rules, workflows, and conventions. It’s typically discovered recursively from the working directory upward (home → project → subdirs). We will mirror these semantics.  ￼

⸻

High-Level Architecture

LangGraph Topology

Even though a single node could “do everything,” a thin orchestrator + tool nodes is more maintainable and easier to test. We’ll use a Supervisor that calls capability nodes (which are tools in LangGraph terms) and returns a consolidated result to the REPL.

[User/CLI]
   ↓
[Supervisor Node]  ←— keeps conversation state and high-level plan
   ├── Tool: FileIndex (walk, ignore rules, metadata)
   ├── Tool: ReadWrite (read/write/patch files, create AGENT/CLAUDE.md)
   ├── Tool: Planner (generate multi-file edit plan)
   ├── Tool: Executor (run commands/files with sandbox & heuristics)
   ├── Tool: Tester (discover & run tests: pytest, npm test, go test, etc.)
   └── Tool: ModelSwitch (set active LLM provider/model)

	•	State (LangGraph state object):
	•	conversation: list[Message]
	•	project_root: Path
	•	active_model: ModelDescriptor (provider, name, max_tokens, cost caps)
	•	policy: SafetyPolicy (execution guard config)
	•	allow_edits: bool (user-approved editing for session)
	•	index: FileIndexSnapshot (paths, sizes, hashes, lang)
	•	context_files: list[Path] (CLAUDE.md, AGENT.md)
	•	run_log_id: str (current session log directory under .bot/)

⸻

CLI & UX

Entry Point
	•	Command: codebot
	•	Default behavior: launch interactive REPL in current working directory.
	•	You can also pass a path: codebot /path/to/project

Slash Commands (REPL)
	•	/init — create CLAUDE.md and AGENT.md if absent; seed with template sections (project overview, setup, conventions, run/test commands).
	•	/plan <goal> — produce a structured multi-file Plan (no writes yet).
	•	/apply — apply the last accepted Plan (requires allow_edits or one-time approval).
	•	/read <path or glob> — show file(s) (summarized for large files).
	•	/write <path> — open an edit sub-mode (or accept a patch).
	•	/exec <cmd> — execute a command via sandbox (e.g., python main.py, pytest -q).
	•	/test — auto-detect and run tests (pytest, npm test, go test, etc.); customizable per project.
	•	/model — show and set active model from supported list.
	•	/allow-edits on|off — gate file writes for the session.
	•	/index — (re)build index; prints summary (#files, size caps, ignored patterns).
	•	/config — print effective config (env, model, ignore rules, limits).
	•	/undo — revert last applied write batch (we store pre-write snapshots).
	•	/log — show path to session logs under .bot/.
	•	/quit

Natural Language
	•	Outside of slash commands, users can type:
“Refactor the CLI parser to support --dry-run, update docs, and add a smoke test,” and the Supervisor will:
	1.	read necessary files, 2) propose a plan, 3) prompt to /apply, 4) optionally /test.

⸻

File & Folder Conventions
	•	Project root: the cwd at launch (or provided path).
	•	Context files:
	•	CLAUDE.md (primary); CLAUDE.local.md (private machine-local);
	•	AGENT.md (OpenAI-friendly mirror).
	•	We read all of these if present; we also support per-subtree CLAUDE.md to scope instructions (mirrors Claude Code behavior).  ￼
	•	Ignore files:
	•	.codebotignore (first-class)
	•	plus .gitignore if present
	•	plus built-in binary and size guards.
	•	Internal data & logs: .bot/ in project root
	•	runs/<timestamp>/ — transcripts, plans, patches, exec logs, stdout/stderr
	•	snapshots/ — pre-write backups for /undo
	•	index.json — current file index summary
	•	config.json — resolved config at run start

⸻

Configuration

.env
	•	OPENAI_API_KEY=...
	•	ANTHROPIC_API_KEY=... (optional; future)
	•	CODEBOT_DEFAULT_MODEL=openai:gpt-4o-mini
	•	CODEBOT_EXEC_NET=deny (deny|allow) default deny network
	•	CODEBOT_EXEC_TIMEOUT=45 (seconds)
	•	CODEBOT_MAX_READ_MB=8
	•	CODEBOT_MAX_WRITE_MB=2

pyproject.toml (high level)
	•	Package: codebot
	•	Entry point: codebot = "codebot.cli:main"
	•	Requires: langgraph, langchain-core (or langgraph only), pydantic, rich, typer, jinja2

⸻

Safety & Execution

Sandbox (default)
	•	subprocess.Popen with:
	•	cwd = project root
	•	pruned environment (pass-through only safe vars: PATH, PYTHONPATH, NODE_OPTIONS if needed)
	•	No network by default (macOS/Linux: set RES_OPTIONS=single-request & use a small wrapper to block sockets; simple v1: warn on “dangerous” commands and allow/deny)
	•	CPU time limit (via resource.setrlimit on Unix), wall-clock timeout, output truncation
	•	Deny sudo, rm -rf /, :(){ :|:& };: patterns, etc., with a regex/AST heuristic + confirmation prompt.
	•	/exec --no-sandbox flag to bypass (prints a red warning, requires explicit confirmation every session).

“Dangerous Execution” Heuristics
	•	Red-flag patterns: package installation, curl | sh, sudo, recursive delete outside project root, binding privileged ports, etc. Bot asks for confirmation unless --assume-yes is active.

⸻

Model Catalog & Switching
	•	Default supported list for /model:
	•	openai:gpt-4o
	•	openai:gpt-4o-mini  ← default
	•	Configurable via .env and an internal registry.
	•	No auto-fallback by default (explicit failures are better during dev). Add an opt-in CODEBOT_FALLBACK=1 to cascade to gpt-4o-mini.

⸻

Planner → Apply Contract

Plan (structured)

class EditAction(BaseModel):
    path: str
    action: Literal["create","patch","replace","delete"]
    justification: str
    patch_unified: str | None  # for "patch"
    content: str | None        # for "create"/"replace"]

class ExecutionAction(BaseModel):
    command: str
    cwd: str | None

class Plan(BaseModel):
    intent: str
    files_to_read: list[str]
    edits: list[EditAction]
    post_checks: list[ExecutionAction]  # tests, linters, smoke runs


	•	/plan produces a Plan.
	•	The REPL prints a concise diff summary and asks to /apply.
	•	/apply performs atomic batch writes (snapshot → apply → verify), then optionally runs post_checks.

⸻

LangGraph Node & Tool Design (Python)

# codebot/graph.py
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel

class BotState(BaseModel):
    conversation: list
    project_root: str
    active_model: str
    allow_edits: bool = False
    index_path: str | None = None
    last_plan: dict | None = None
    run_log_id: str | None = None
    policy: dict = {}

def build_graph(tools):
    g = StateGraph(BotState)

    def supervisor(state: BotState):
        # route based on last user command / NL intent
        # call tools[].* as needed; update state.last_plan, etc.
        return state

    g.add_node("supervisor", supervisor)
    g.add_edge(START, "supervisor")
    g.add_edge("supervisor", END)
    g.add_conditional_edges("supervisor", lambda s: [])  # single-hop loop per turn
    return g.compile()

# codebot/tools/file_index.py
class FileIndex:
    def __init__(self, root: Path, ignores: IgnoreRules, caps: Caps): ...
    def build(self) -> FileIndexSnapshot: ...
    def summarize(self) -> dict: ...

# codebot/tools/read_write.py
class ReadWrite:
    def read(self, path: str, mode="auto") -> str: ...
    def write(self, path: str, content: str) -> None: ...
    def patch(self, path: str, unified_diff: str) -> PatchResult: ...
    def snapshot(self) -> SnapshotRef: ...
    def restore(self, snapshot: SnapshotRef) -> None: ...

# codebot/tools/planner.py
class Planner:
    def make_plan(self, goal: str, index: FileIndexSnapshot, context_docs: list[str], model: LLM) -> Plan: ...

# codebot/tools/executor.py
class Executor:
    def run(self, command: str, timeout: int, sandbox: SandboxPolicy) -> ExecResult: ...
    def is_dangerous(self, command: str) -> tuple[bool, str]: ...

# codebot/tools/tester.py
class Tester:
    def detect(self) -> list[str]:  # returns commands to run
    def run_all(self) -> list[ExecResult]: ...

# codebot/llm.py
class ModelDescriptor(BaseModel):
    provider: Literal["openai","anthropic"]
    name: str
    max_output_tokens: int

class LLM:
    def __init__(self, descriptor: ModelDescriptor): ...
    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict: ...

# codebot/cli.py
import typer
def main(path: str = typer.Argument(None)): ...

CLAUDE.md / AGENT.md Template (created by /init)

Content sections:
	1.	Project Overview (1–2 paragraphs)
	2.	Tech Stack & Conventions (language versions, code style)
	3.	How to Run (dev servers, CLI, dataset paths)
	4.	How to Test / Lint (commands)
	5.	Architecture Map (bulleted directories + purposes)
	6.	Editing Rules (file preferences, patterns to avoid, naming)
	7.	Non-negotiables (security, performance budgets)
	8.	Task Guide (how the bot should plan/apply; prefer patches; always run smoke test)
	9.	Changelog Links (optional)

We will also support nested CLAUDE.md for submodules (docs pulled preferentially for that subtree).  ￼

⸻

Indexing & Token Discipline
	•	Indexing: Walk the tree respecting .codebotignore and .gitignore; record file path, size, type (via extension & lightweight magic), hash.
	•	Read policy:
	•	Small text files: inline content.
	•	Large files: chunked summaries with file-level embeddings optional later.
	•	“Clever search”: Before reading, build a query plan from the user’s request and CLAUDE.md rules to select only relevant files by name, path heuristics, and language signals; escalate to content reads only as needed.

⸻

Approval Flow
	•	On first write in a new session: prompt Allow edits for this session? (y/N)
	•	If approved, allow_edits=True for the REPL; user can /allow-edits off anytime.

⸻

Test Discovery (v1)
	•	If pytest.ini or tests/ exists → pytest -q
	•	If package.json with script test → npm test --silent
	•	If go.mod → go test ./...
	•	Users can override via .bot/config.json:

{
  "commands": {
    "build": "make build",
    "test": "pytest -q",
    "lint": "ruff check ."
  }
}


⸻

Logging & Undo
	•	Logs: .bot/runs/<ts>/
	•	transcript.ndjson (messages & tool calls)
	•	plan.json
	•	diffs/ (one file per edit)
	•	exec/ (stdout/stderr per command)
	•	Undo: Before each batch write we create .bot/snapshots/<id>/ with originals; /undo restores last batch.

⸻

Minimal Public Interfaces (for Codex/Claude Code to generate)

# Public API
class CodeBot:
    def __init__(self, project_root: Path, model: str | None = None): ...
    def repl(self): ...
    def command(self, line: str): ...
    def handle_natural_language(self, text: str): ...

# Tool Facade for LangGraph
class Tools:
    file_index: FileIndex
    io: ReadWrite
    planner: Planner
    executor: Executor
    tester: Tester
    llm: LLM

Initial Non-Goals (v1)
	•	No Git integration (we rely on snapshots/undo).
	•	No Docker; no cross-OS testing.
	•	No embeddings/vector store (may add later).
	•	No multi-repo orchestration.

⸻

Test Plan (v1)
	1.	Unit

	•	FileIndex.build() respects .codebotignore and .gitignore
	•	ReadWrite.patch() applies unified diff reliably (handles CRLF/UTF-8)
	•	Executor.is_dangerous() flags risky commands (table-driven tests)
	•	Tester.detect() chooses correct runner per project
	•	LLM.complete() selects correct provider headers and token limits

	2.	Integration

	•	/init creates CLAUDE.md & AGENT.md with template
	•	/plan → /apply modifies multiple files and writes diffs/logs
	•	/exec & /test time out properly and store outputs
	•	/undo restores prior state

	3.	E2E

	•	Create a sample repo (Python lib with tests); ask for a feature; ensure plan→apply→test passes and logs are correct.

⸻

Roadmap (Post-v1)
	•	Optional Anthropic provider (mirror /model support)
	•	Git branch & commit integration
	•	Simple RAG: file-embedding index for large repos
	•	Structured tool calling with JSON-schema functions for plan generation
	•	“Safe-apply” mode: generates patches only, user applies manually

1) Directory layout (suggested)
pitcrew/
├─ pyproject.toml
├─ README.md
├─ .env.example
├─ .gitignore
├─ pitcrew/
│  ├─ __init__.py
│  ├─ cli.py
│  ├─ graph.py
│  ├─ state.py
│  ├─ llm.py
│  ├─ config.py
│  ├─ constants.py
│  ├─ templates/
│  │  ├─ AGENT.md.j2
│  │  └─ CLAUDE.md.j2
│  ├─ tools/
│  │  ├─ __init__.py
│  │  ├─ file_index.py
│  │  ├─ read_write.py
│  │  ├─ planner.py
│  │  ├─ executor.py
│  │  └─ tester.py
│  └─ utils/
│     ├─ diffs.py
│     └─ ignore.py
└─ tests/
   ├─ test_index.py
   ├─ test_patching.py
   └─ test_executor.py