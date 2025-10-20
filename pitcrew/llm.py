"""LLM abstraction layer for Anthropic Claude models."""

from dataclasses import dataclass
from typing import Any, Generator, Literal, Optional

from anthropic import Anthropic

from pitcrew.constants import SUPPORTED_MODELS


@dataclass
class ModelDescriptor:
    """Descriptor for an LLM model."""

    provider: Literal["anthropic"]
    name: str
    max_output_tokens: int
    temperature: float = 0.7


class LLM:
    """Anthropic Claude LLM interface."""

    def __init__(self, descriptor: ModelDescriptor, api_key: str):
        """Initialize LLM client.

        Args:
            descriptor: Model descriptor
            api_key: Anthropic API key
        """
        self.descriptor = descriptor
        self.api_key = api_key

        if descriptor.provider != "anthropic":
            raise ValueError(f"Only Anthropic models are supported. Got: {descriptor.provider}")

        self.client = Anthropic(api_key=api_key)

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> dict[str, Any]:
        """Generate a completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions
            temperature: Optional temperature override
            max_tokens: Optional max tokens override

        Returns:
            Response dict with 'content', optional 'tool_calls'
        """
        temp = temperature if temperature is not None else self.descriptor.temperature
        max_tok = max_tokens if max_tokens is not None else self.descriptor.max_output_tokens

        return self._complete_anthropic(messages, tools, temp, max_tok)

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """Generate a streaming completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions
            temperature: Optional temperature override
            max_tokens: Optional max tokens override

        Yields:
            Text chunks as they arrive
        """
        temp = temperature if temperature is not None else self.descriptor.temperature
        max_tok = max_tokens if max_tokens is not None else self.descriptor.max_output_tokens

        yield from self._stream_anthropic(messages, tools, temp, max_tok)

    def _complete_anthropic(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Complete using Anthropic API."""
        # Anthropic requires system messages to be separate
        system_messages = [m["content"] for m in messages if m["role"] == "system"]
        system = "\n\n".join(system_messages) if system_messages else None

        # Filter out system messages and convert to Anthropic format
        import copy
        import json as json_debug

        print(f"\n=== ANTHROPIC CONVERSION START ===")
        print(f"Input messages count: {len(messages)}")

        # Check if INPUT messages have tool_calls
        for i, m in enumerate(messages):
            if isinstance(m, dict) and "tool_calls" in m:
                print(f"⚠️  INPUT Message {i} has tool_calls! Keys: {list(m.keys())}")

        chat_messages = []
        for m in messages:
            if m["role"] == "system":
                continue

            # Convert assistant messages with tool_calls to Anthropic format
            if m["role"] == "assistant" and "tool_calls" in m:
                content = []
                if m.get("content"):
                    content.append({"type": "text", "text": m["content"]})
                for tc in m["tool_calls"]:
                    # Parse arguments if string
                    import json
                    arguments = tc["arguments"]
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            arguments = {}

                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": arguments
                    })
                # Create new dict WITHOUT tool_calls
                chat_messages.append({"role": "assistant", "content": content})
            elif m["role"] == "assistant":
                # Regular assistant message - deep copy to avoid mutations
                chat_messages.append(copy.deepcopy(m))
            elif m["role"] == "user":
                # User messages may already be in Anthropic format (with tool_result)
                # Deep copy to avoid mutations
                chat_messages.append(copy.deepcopy(m))
            else:
                # Shouldn't happen but keep it
                chat_messages.append(copy.deepcopy(m))

        # Final validation: ensure no tool_calls in any message
        print(f"\n=== FINAL VALIDATION ===")
        print(f"Output chat_messages count: {len(chat_messages)}")

        for i, msg in enumerate(chat_messages):
            if isinstance(msg, dict):
                if "tool_calls" in msg:
                    print(f"❌ ERROR: Found tool_calls in chat_messages[{i}]")
                    print(f"   Keys: {list(msg.keys())}")
                    print(f"   Full message: {json_debug.dumps(msg, indent=2)}")
                    # Force remove it
                    msg = {k: v for k, v in msg.items() if k != "tool_calls"}
                    chat_messages[i] = msg
                else:
                    print(f"✓ Message {i}: role={msg.get('role')}, has tool_calls=False")

        # Create a completely new list to avoid any reference issues
        # Deep copy but explicitly exclude 'tool_calls' key
        clean_messages = []
        for msg in chat_messages:
            if isinstance(msg, dict):
                # Create brand new dict excluding tool_calls
                clean_msg = {k: copy.deepcopy(v) for k, v in msg.items() if k != "tool_calls"}
                clean_messages.append(clean_msg)
            else:
                clean_messages.append(copy.deepcopy(msg))

        print(f"\n=== CREATING KWARGS ===")
        print(f"Clean messages count: {len(clean_messages)}")
        for i, msg in enumerate(clean_messages):
            if isinstance(msg, dict):
                print(f"  Message {i} keys: {list(msg.keys())}")
                # Check if content is a list (tool use)
                if isinstance(msg.get("content"), list):
                    print(f"    Content is list with {len(msg['content'])} items")
                    for j, item in enumerate(msg["content"]):
                        if isinstance(item, dict):
                            print(f"      Item {j} type: {item.get('type')}, keys: {list(item.keys())}")
                elif isinstance(msg.get("content"), str):
                    print(f"    Content is string ({len(msg['content'])} chars)")
            else:
                print(f"  Message {i}: not a dict")

        kwargs: dict[str, Any] = {
            "model": self.descriptor.name,
            "messages": clean_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system:
            kwargs["system"] = system

        if tools:
            # Convert OpenAI tool format to Anthropic format
            kwargs["tools"] = self._convert_tools_to_anthropic(tools)

        print(f"\n=== CALLING ANTHROPIC API ===")
        print(f"Model: {kwargs['model']}")
        print(f"Messages: {len(kwargs['messages'])}")
        print(f"Has tools: {tools is not None}")

        try:
            response = self.client.messages.create(**kwargs)
        except Exception as e:
            print(f"\n!!! ANTHROPIC API ERROR !!!")
            print(f"Error: {e}")
            print(f"\nMessages being sent ({len(chat_messages)} total):")
            import json as json_mod
            for i, msg in enumerate(chat_messages):
                print(f"\n--- Message {i} ---")
                print(json_mod.dumps(msg, indent=2))
            raise

        result: dict[str, Any] = {
            "role": "assistant",
            "content": "",
        }

        # Extract content and tool calls
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                result["content"] += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        if tool_calls:
            result["tool_calls"] = tool_calls

        return result

    def _convert_tools_to_anthropic(self, openai_tools: list[dict]) -> list[dict]:
        """Convert OpenAI tool format to Anthropic format.

        Args:
            openai_tools: List of OpenAI tool definitions

        Returns:
            List of Anthropic tool definitions
        """
        anthropic_tools = []
        for tool in openai_tools:
            if tool["type"] == "function":
                func = tool["function"]
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {}),
                })
        return anthropic_tools

    @classmethod
    def parse_model_string(cls, model_str: str) -> ModelDescriptor:
        """Parse model string into ModelDescriptor.

        Args:
            model_str: Model string (e.g., "openai:gpt-4o-mini")

        Returns:
            ModelDescriptor

        Raises:
            ValueError: If model string is invalid
        """
        if model_str not in SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model: {model_str}. "
                f"Supported: {', '.join(SUPPORTED_MODELS.keys())}"
            )

        model_config = SUPPORTED_MODELS[model_str]
        return ModelDescriptor(
            provider=model_config["provider"],
            name=model_config["name"],
            max_output_tokens=model_config["max_output_tokens"],
        )

    def _stream_anthropic(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict]],
        temperature: float,
        max_tokens: int,
    ) -> Generator[str, None, None]:
        """Stream using Anthropic API."""
        # Anthropic requires system messages to be separate
        system_messages = [m["content"] for m in messages if m["role"] == "system"]
        system = "\n\n".join(system_messages) if system_messages else None

        # Filter out system messages from main messages
        chat_messages = [m for m in messages if m["role"] != "system"]

        kwargs: dict[str, Any] = {
            "model": self.descriptor.name,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system:
            kwargs["system"] = system

        if tools:
            # Convert OpenAI tool format to Anthropic format
            kwargs["tools"] = self._convert_tools_to_anthropic(tools)

        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text

    @classmethod
    def list_models(cls) -> list[str]:
        """List all supported model strings.

        Returns:
            List of model strings
        """
        return list(SUPPORTED_MODELS.keys())
