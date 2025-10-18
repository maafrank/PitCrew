"""State models for LangGraph."""

from typing import TypedDict, Optional, Annotated
from operator import add


class BotState(TypedDict):
    """The state object passed through the LangGraph workflow.

    Attributes:
        conversation: List of conversation messages
        project_root: Absolute path to project root
        active_model: Model string (e.g., "openai:gpt-4o-mini")
        allow_edits: Whether file edits are permitted this session
        index: File index snapshot (dict)
        last_plan: Most recent plan generated (dict)
        run_log_id: Session log directory ID
        policy: Execution policy settings
        context_files: Paths to CLAUDE.md, AGENT.md, etc.
    """

    conversation: Annotated[list[dict], add]
    project_root: str
    active_model: str
    allow_edits: bool
    index: Optional[dict]
    last_plan: Optional[dict]
    run_log_id: Optional[str]
    policy: dict
    context_files: Annotated[list[str], add]
