"""LLM abstraction layer for multiple providers."""

from dataclasses import dataclass
from typing import Any, Literal, Optional

from anthropic import Anthropic
from openai import OpenAI

from pitcrew.constants import SUPPORTED_MODELS


@dataclass
class ModelDescriptor:
    """Descriptor for an LLM model."""

    provider: Literal["openai", "anthropic"]
    name: str
    max_output_tokens: int
    temperature: float = 0.7


class LLM:
    """Unified LLM interface for multiple providers."""

    def __init__(self, descriptor: ModelDescriptor, api_key: str):
        """Initialize LLM client.

        Args:
            descriptor: Model descriptor
            api_key: API key for the provider
        """
        self.descriptor = descriptor
        self.api_key = api_key

        if descriptor.provider == "openai":
            self.client = OpenAI(api_key=api_key)
        elif descriptor.provider == "anthropic":
            self.client = Anthropic(api_key=api_key)
        else:
            raise ValueError(f"Unsupported provider: {descriptor.provider}")

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

        if self.descriptor.provider == "openai":
            return self._complete_openai(messages, tools, temp, max_tok)
        elif self.descriptor.provider == "anthropic":
            return self._complete_anthropic(messages, tools, temp, max_tok)

    def _complete_openai(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Complete using OpenAI API."""
        kwargs: dict[str, Any] = {
            "model": self.descriptor.name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)

        message = response.choices[0].message

        result: dict[str, Any] = {
            "content": message.content or "",
            "role": "assistant",
        }

        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in message.tool_calls
            ]

        return result

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

        response = self.client.messages.create(**kwargs)

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

    @classmethod
    def list_models(cls) -> list[str]:
        """List all supported model strings.

        Returns:
            List of model strings
        """
        return list(SUPPORTED_MODELS.keys())
