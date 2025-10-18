"""Autonomous handler for plan-execute-test loop."""

from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from pitcrew.conversation import ConversationContext
    from pitcrew.graph import PitCrewGraph

console = Console()


class AutonomousHandler:
    """Handles autonomous execution: plan -> apply -> test."""

    def __init__(self, graph: "PitCrewGraph", context: "ConversationContext"):
        """Initialize autonomous handler.

        Args:
            graph: PitCrewGraph instance
            context: Conversation context
        """
        self.graph = graph
        self.context = context

    def handle(self, goal: str, auto_apply: bool = False) -> str:
        """Handle an autonomous request.

        Args:
            goal: User's goal/request
            auto_apply: Whether to auto-apply without asking

        Returns:
            Result summary
        """
        results = []

        # 1. Generate plan
        console.print(f"\n[dim]🤔 Planning: {goal}[/dim]")
        try:
            plan_dict, summary = self.graph.handle_plan(goal)
            results.append(f"📋 **Plan Generated:**\n{summary}")

            # Update context
            self.context.update_plan(plan_dict)

        except Exception as e:
            return f"❌ Failed to generate plan: {str(e)}"

        # 2. Ask for approval (unless auto_apply or edits already allowed)
        if not auto_apply and not self.graph.read_write.project_root:
            # Check if we have permission
            from pitcrew.cli import REPL

            # This will be set by REPL
            pass

        should_apply = auto_apply
        if not auto_apply:
            response = console.input("\n[yellow]Apply this plan? (y/N):[/yellow] ").lower()
            should_apply = response == "y"

        if not should_apply:
            results.append("\n⏸️  Plan saved but not applied. Use `/apply` to execute it later.")
            return "\n\n".join(results)

        # 3. Apply plan
        console.print("\n[dim]✏️  Applying changes...[/dim]")
        try:
            apply_result = self.graph.handle_apply(plan_dict)
            results.append(f"\n✏️  **Changes Applied:**\n{apply_result}")
        except Exception as e:
            results.append(f"\n❌ Failed to apply changes: {str(e)}")
            results.append("\n💡 Tip: Use `/undo` if you need to rollback.")
            return "\n\n".join(results)

        # 4. Run tests (if available)
        console.print("\n[dim]🧪 Running tests...[/dim]")
        try:
            test_result = self.graph.handle_test()
            results.append(f"\n🧪 **Test Results:**\n{test_result}")

            # Update context with test results
            # Analyze if tests passed
            if "failed" in test_result.lower() or "error" in test_result.lower():
                results.append(
                    "\n⚠️  **Tests failed!** You may want to:\n"
                    "- Use `/undo` to rollback\n"
                    "- Ask me to fix the issues\n"
                    "- Review the changes manually"
                )
            elif "No tests found" in test_result:
                results.append(
                    "\n📝 **Note:** No tests were found. Consider adding tests for the new code."
                )
            else:
                results.append("\n✅ **Success!** All checks passed.")

        except Exception as e:
            results.append(f"\n⚠️  Could not run tests: {str(e)}")

        return "\n\n".join(results)
