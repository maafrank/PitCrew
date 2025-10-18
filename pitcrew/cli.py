"""CLI and REPL for PitCrew."""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from pitcrew.config import Config
from pitcrew.graph import PitCrewGraph
from pitcrew.llm import LLM
from pitcrew.utils.logging import SessionLogger

app = typer.Typer(help="PitCrew - Terminal Code Editing Bot")
console = Console()


class REPL:
    """Interactive REPL for PitCrew."""

    def __init__(self, project_root: Path, config: Config):
        """Initialize REPL.

        Args:
            project_root: Project root directory
            config: Configuration object
        """
        self.project_root = project_root
        self.config = config
        self.graph = PitCrewGraph(project_root, config)
        self.logger = SessionLogger(project_root)
        self.graph.logger = self.logger

        self.last_plan = None
        self.allow_edits = False
        self.running = True

    def start(self) -> None:
        """Start the REPL."""
        console.print(Panel.fit(
            "[bold cyan]PitCrew[/bold cyan] - Terminal Code Editing Bot\n"
            f"Project: {self.project_root}\n"
            f"Model: {self.config.default_model}\n"
            "\n"
            "Type /help for commands or /quit to exit",
            border_style="cyan"
        ))

        # Load initial index
        console.print("\n[dim]Building file index...[/dim]")
        index = self.graph.file_index.load_from_disk()
        if not index:
            index = self.graph.file_index.build()
            self.graph.file_index.save_to_disk(index)
        summary = self.graph.file_index.summarize(index)
        console.print(f"[dim]{summary}[/dim]\n")

        # Main REPL loop
        while self.running:
            try:
                user_input = console.input("[bold cyan]pitcrew>[/bold cyan] ").strip()

                if not user_input:
                    continue

                self.logger.log_message("user", user_input)
                self.handle_input(user_input)

            except KeyboardInterrupt:
                console.print("\n[dim]Use /quit to exit[/dim]")
                continue
            except EOFError:
                break

        console.print("\n[cyan]Goodbye![/cyan]")

    def handle_input(self, user_input: str) -> None:
        """Handle user input (command or natural language).

        Args:
            user_input: User input string
        """
        if user_input.startswith("/"):
            self.handle_command(user_input)
        else:
            self.handle_natural_language(user_input)

    def handle_command(self, command: str) -> None:
        """Handle slash command.

        Args:
            command: Command string (starting with /)
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        try:
            if cmd == "/help":
                self.show_help()
            elif cmd == "/quit" or cmd == "/exit":
                self.running = False
            elif cmd == "/init":
                result = self.graph.handle_init()
                console.print(result)
            elif cmd == "/index":
                result = self.graph.handle_index()
                console.print(result)
            elif cmd == "/read":
                if not args:
                    console.print("[red]Usage: /read <path>[/red]")
                    return
                result = self.graph.handle_read(args)
                # Display with syntax highlighting
                if not result.startswith("Error"):
                    lines = result.split("\n", 1)
                    console.print(f"[bold]{lines[0]}[/bold]")
                    if len(lines) > 1:
                        try:
                            syntax = Syntax(lines[1], "python", theme="monokai")
                            console.print(syntax)
                        except Exception:
                            console.print(lines[1])
                else:
                    console.print(f"[red]{result}[/red]")
            elif cmd == "/plan":
                if not args:
                    console.print("[red]Usage: /plan <goal>[/red]")
                    return
                console.print(f"[dim]Generating plan for: {args}[/dim]\n")
                plan_dict, summary = self.graph.handle_plan(args)
                self.last_plan = plan_dict
                console.print(Panel(summary, title="Plan", border_style="green"))
                console.print("\n[yellow]Use /apply to execute this plan[/yellow]")
            elif cmd == "/apply":
                if not self.last_plan:
                    console.print("[red]No plan to apply. Use /plan first.[/red]")
                    return
                if not self.allow_edits:
                    response = console.input(
                        "[yellow]Allow edits for this session? (y/N):[/yellow] "
                    ).lower()
                    if response != "y":
                        console.print("[red]Edits not allowed. Plan not applied.[/red]")
                        return
                    self.allow_edits = True
                console.print("[dim]Applying plan...[/dim]\n")
                result = self.graph.handle_apply(self.last_plan)
                console.print(result)
            elif cmd == "/exec":
                if not args:
                    console.print("[red]Usage: /exec <command>[/red]")
                    return
                console.print(f"[dim]Executing: {args}[/dim]\n")
                result = self.graph.handle_exec(args)
                console.print(result)
            elif cmd == "/test":
                console.print("[dim]Running tests...[/dim]\n")
                result = self.graph.handle_test()
                console.print(result)
            elif cmd == "/undo":
                result = self.graph.handle_undo()
                console.print(result)
            elif cmd == "/allow-edits":
                if args.lower() == "on":
                    self.allow_edits = True
                    console.print("[green]Edits enabled for this session[/green]")
                elif args.lower() == "off":
                    self.allow_edits = False
                    console.print("[yellow]Edits disabled for this session[/yellow]")
                else:
                    console.print(f"[dim]Edits currently: {'enabled' if self.allow_edits else 'disabled'}[/dim]")
                    console.print("[dim]Usage: /allow-edits on|off[/dim]")
            elif cmd == "/model":
                if args:
                    # Switch model
                    try:
                        descriptor = LLM.parse_model_string(args)
                        self.config.default_model = args
                        # Reinitialize LLM
                        api_key = (
                            self.config.openai_api_key
                            if descriptor.provider == "openai"
                            else self.config.anthropic_api_key
                        )
                        self.graph.llm = LLM(descriptor, api_key)
                        self.graph.planner.llm = self.graph.llm
                        console.print(f"[green]Switched to model: {args}[/green]")
                    except ValueError as e:
                        console.print(f"[red]{e}[/red]")
                else:
                    # Show current model and list available
                    console.print(f"[dim]Current model: {self.config.default_model}[/dim]")
                    console.print("\nAvailable models:")
                    for model in LLM.list_models():
                        console.print(f"  - {model}")
            elif cmd == "/config":
                config_dict = self.config.to_dict()
                console.print(Panel(
                    "\n".join(f"{k}: {v}" for k, v in config_dict.items()),
                    title="Configuration",
                    border_style="blue"
                ))
            elif cmd == "/log":
                log_path = self.logger.get_log_path()
                console.print(f"[dim]Session logs: {log_path}[/dim]")
            else:
                console.print(f"[red]Unknown command: {cmd}[/red]")
                console.print("[dim]Type /help for available commands[/dim]")

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            import traceback
            traceback.print_exc()

    def handle_natural_language(self, text: str) -> None:
        """Handle natural language input.

        Args:
            text: User's natural language request
        """
        console.print("[yellow]Natural language processing not yet implemented.[/yellow]")
        console.print("[dim]For now, use /plan <your goal> to generate a plan.[/dim]")

    def show_help(self) -> None:
        """Show help message."""
        help_text = """
**Available Commands:**

- `/init` - Create CLAUDE.md and AGENT.md files
- `/plan <goal>` - Generate a structured edit plan
- `/apply` - Apply the last generated plan
- `/read <path>` - Read a file
- `/exec <cmd>` - Execute a command
- `/test` - Auto-detect and run tests
- `/index` - Rebuild file index
- `/undo` - Revert last applied changes
- `/allow-edits on|off` - Toggle edit permissions
- `/model [name]` - Show or switch LLM model
- `/config` - Show current configuration
- `/log` - Show session log path
- `/help` - Show this help message
- `/quit` - Exit PitCrew

**Examples:**

```
/plan Add a function to calculate fibonacci numbers and write tests
/read src/main.py
/exec python -m pytest tests/
/model openai:gpt-4o
```
        """
        console.print(Markdown(help_text))


@app.command()
def main(
    path: Optional[str] = typer.Argument(
        None,
        help="Project path (default: current directory)"
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model", "-m",
        help="Model to use (e.g., openai:gpt-4o-mini)"
    ),
) -> None:
    """Start PitCrew interactive session."""
    # Determine project root
    project_root = Path(path).resolve() if path else Path.cwd()

    if not project_root.exists():
        console.print(f"[red]Error: Path does not exist: {project_root}[/red]")
        sys.exit(1)

    if not project_root.is_dir():
        console.print(f"[red]Error: Path is not a directory: {project_root}[/red]")
        sys.exit(1)

    # Load configuration
    try:
        config = Config.load(project_root)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)

    # Override model if specified
    if model:
        config.default_model = model

    # Validate configuration
    errors = config.validate()
    if errors:
        console.print("[red]Configuration errors:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        sys.exit(1)

    # Start REPL
    try:
        repl = REPL(project_root, config)
        repl.start()
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    app()
