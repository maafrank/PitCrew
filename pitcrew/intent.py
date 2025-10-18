"""Intent detection for natural language input."""

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field

from pitcrew.llm import LLM


class Intent(BaseModel):
    """Detected user intent."""

    action: Literal["query", "plan", "read", "execute", "test", "help", "config"] = Field(
        description="The type of action the user wants to perform"
    )
    target: Optional[str] = Field(
        None, description="The target of the action (file path, command, or description)"
    )
    confidence: float = Field(description="Confidence score 0-1", ge=0.0, le=1.0)
    reasoning: str = Field(description="Explanation of why this intent was detected")


class IntentDetector:
    """Detects user intent from natural language input."""

    def __init__(self, llm: LLM):
        """Initialize intent detector.

        Args:
            llm: LLM instance to use for detection
        """
        self.llm = llm

    def detect(self, user_input: str, context_summary: str = "") -> Intent:
        """Detect intent from user input.

        Args:
            user_input: User's natural language input
            context_summary: Summary of conversation context

        Returns:
            Detected Intent
        """
        system_prompt = self._build_system_prompt()

        user_prompt = f"""Detect the user's intent from their input.

User input: "{user_input}"

{f"Recent context: {context_summary}" if context_summary else ""}

Analyze the input and determine:
1. What action they want (query, plan, read, execute, test, help, config)
2. The target (if applicable)
3. Your confidence level
4. Brief reasoning

Action types:
- query: Asking a question about the project (e.g., "What does this do?", "Tell me about...")
- plan: Requesting code changes (e.g., "Add a function", "Fix the bug", "Refactor...")
- read: Wanting to see file contents (e.g., "Show me main.py", "What's in the config?")
- execute: Running a command (e.g., "Run tests", "Execute the script")
- test: Specifically running tests
- help: Asking for help or list of commands
- config: Asking about configuration or settings

Use the detect_intent function to respond."""

        # Define the function schema
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "detect_intent",
                    "description": "Detect the user's intent from their natural language input",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["query", "plan", "read", "execute", "test", "help", "config"],
                                "description": "The type of action",
                            },
                            "target": {
                                "type": "string",
                                "description": "Target of the action (optional)",
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                                "description": "Confidence score",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Brief explanation of the detection",
                            },
                        },
                        "required": ["action", "confidence", "reasoning"],
                    },
                },
            }
        ]

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            response = self.llm.complete(messages, tools=tools, temperature=0.2)

            # Extract intent from tool call
            if "tool_calls" in response and response["tool_calls"]:
                tool_call = response["tool_calls"][0]
                if isinstance(tool_call["arguments"], str):
                    args = json.loads(tool_call["arguments"])
                else:
                    args = tool_call["arguments"]

                return Intent(**args)

            # Fallback: try to parse from content
            return self._fallback_detection(user_input)

        except Exception as e:
            # Fallback detection on error
            return self._fallback_detection(user_input, error=str(e))

    def _build_system_prompt(self) -> str:
        """Build the system prompt for intent detection.

        Returns:
            System prompt string
        """
        return """You are an intent detection system for PitCrew, an AI code editing assistant.

Your job is to understand what the user wants to do and categorize it into one of these actions:

- **query**: User is asking a question about the project, code, or how something works
- **plan**: User wants to make changes to code (add, modify, delete, refactor)
- **read**: User wants to see the contents of a file or module
- **execute**: User wants to run a specific command
- **test**: User wants to run tests
- **help**: User needs help with commands or usage
- **config**: User is asking about configuration or settings

Be accurate and provide high confidence scores only when intent is clear.
If the input is ambiguous, choose the most likely intent and explain your reasoning."""

    def _fallback_detection(self, user_input: str, error: Optional[str] = None) -> Intent:
        """Simple rule-based fallback detection.

        Args:
            user_input: User input
            error: Optional error message

        Returns:
            Intent based on keyword matching
        """
        user_lower = user_input.lower()

        # Query patterns
        if any(
            kw in user_lower
            for kw in ["what", "how", "why", "tell me", "explain", "describe", "about"]
        ):
            return Intent(
                action="query",
                target=user_input,
                confidence=0.6,
                reasoning="Question words detected (fallback detection)",
            )

        # Plan patterns
        if any(
            kw in user_lower
            for kw in [
                "add",
                "create",
                "make",
                "build",
                "implement",
                "fix",
                "refactor",
                "update",
                "change",
                "modify",
            ]
        ):
            return Intent(
                action="plan",
                target=user_input,
                confidence=0.6,
                reasoning="Code modification keywords detected (fallback)",
            )

        # Read patterns
        if any(kw in user_lower for kw in ["show", "read", "display", "open", "view"]):
            return Intent(
                action="read",
                target=user_input,
                confidence=0.5,
                reasoning="File viewing keywords detected (fallback)",
            )

        # Test patterns
        if any(kw in user_lower for kw in ["test", "pytest", "npm test"]):
            return Intent(
                action="test",
                target=None,
                confidence=0.7,
                reasoning="Test keywords detected (fallback)",
            )

        # Help patterns
        if any(kw in user_lower for kw in ["help", "command", "how to use"]):
            return Intent(
                action="help",
                target=None,
                confidence=0.7,
                reasoning="Help keywords detected (fallback)",
            )

        # Default to query
        return Intent(
            action="query",
            target=user_input,
            confidence=0.3,
            reasoning=f"Unclear intent, defaulting to query{f' (error: {error})' if error else ''}",
        )
