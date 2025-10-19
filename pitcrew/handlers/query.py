"""Query handler for answering questions about the project."""

import json
from typing import TYPE_CHECKING, Generator

from rich.console import Console

from pitcrew.llm import LLM

if TYPE_CHECKING:
    from pitcrew.conversation import ConversationContext
    from pitcrew.graph import PitCrewGraph

console = Console()


class QueryHandler:
    """Handles user queries about the project."""

    def __init__(self, graph: "PitCrewGraph", llm: LLM):
        """Initialize query handler.

        Args:
            graph: PitCrewGraph instance
            llm: LLM instance
        """
        self.graph = graph
        self.llm = llm

    def _get_tools(self) -> list[dict]:
        """Get tool definitions for the LLM.

        Returns:
            List of tool definitions in OpenAI format
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files and directories in the project or a specific directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Directory path to list (default: project root). Use '.' for project root.",
                            }
                        },
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_file_summary",
                    "description": "Get an AI-generated summary of a file including its purpose, key classes, functions, and structure. USE THIS instead of read_file for understanding code.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the file to summarize",
                            }
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the FULL raw contents of a file. Only use when you need the exact code or full content. For understanding, use get_file_summary instead.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the file to read",
                            }
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Search for code patterns or text in the project files",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Text or regex pattern to search for",
                            }
                        },
                        "required": ["pattern"]
                    }
                }
            },
        ]

    def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool call.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution result as string
        """
        try:
            if tool_name == "list_files":
                path = arguments.get("path", ".")
                result = self.graph.handle_exec(f"ls -la {path}")
                return result

            elif tool_name == "get_file_summary":
                path = arguments.get("path")
                if not path:
                    return "Error: path is required"
                return self._summarize_file(path)

            elif tool_name == "read_file":
                path = arguments.get("path")
                if not path:
                    return "Error: path is required"
                result = self.graph.handle_read(path)
                return result

            elif tool_name == "search_code":
                pattern = arguments.get("pattern")
                if not pattern:
                    return "Error: pattern is required"
                result = self.graph.handle_exec(f"grep -r '{pattern}' . --include='*.py' || echo 'No matches found'")
                return result

            else:
                return f"Error: Unknown tool {tool_name}"

        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    def _summarize_file(self, path: str) -> str:
        """Generate an AI summary of a file using a standalone LLM call.

        Args:
            path: File path to summarize

        Returns:
            Structured summary of the file
        """
        # Read the entire file
        success, content, error = self.graph.read_write.read(path)
        if not success:
            return f"Error reading {path}: {error}"

        # Create a standalone LLM call with NO conversation context
        summary_prompt = f"""Analyze this code file and provide a detailed structured summary.

File: {path}

Content:
```
{content}
```

Provide a comprehensive summary in this format:

**Purpose:**
[1-2 sentence description of what this file does and its role in the project]

**Classes:**
For each class, provide:
- Class name and purpose
- Key methods with signatures (name, parameters, return type)
- Important attributes

**Functions:**
For each standalone function, provide:
- Function signature (name, parameters, return type)
- Brief description of what it does
- Any notable side effects or dependencies

**Dependencies:**
- External libraries/imports
- Internal module dependencies

**Configuration/Constants:**
- Important constants or configuration values
- Environment variables used

**Notable Patterns:**
- Design patterns used
- Architectural decisions
- Error handling approach
- Any important algorithms or logic

Focus on providing actionable information that helps a developer understand and work with this file."""

        try:
            # Standalone LLM call - no tools, no conversation history
            messages = [
                {"role": "user", "content": summary_prompt}
            ]
            # No max_tokens limit - let it generate as much as needed
            response = self.llm.complete(messages, temperature=0.3)
            return response["content"]
        except Exception as e:
            # Fallback to basic file info
            return f"File: {path}\nSize: {len(content)} chars\n[Summary generation failed: {e}]"

    def _add_tool_results_to_messages(
        self,
        messages: list[dict],
        response: dict,
        tool_results: dict[str, str]
    ) -> None:
        """Add tool calls and results to messages list.

        Args:
            messages: Messages list to append to
            response: LLM response with tool_calls
            tool_results: Map of tool_call_id to result string
        """
        # Format depends on provider - add in native format to avoid conversion issues
        if self.llm.descriptor.provider == "anthropic":
            # Anthropic format: assistant message with tool_use content blocks
            content = []
            if response.get("content"):
                content.append({"type": "text", "text": response["content"]})

            for tool_call in response["tool_calls"]:
                # Parse arguments if needed
                import json
                arguments = tool_call["arguments"]
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                content.append({
                    "type": "tool_use",
                    "id": tool_call["id"],
                    "name": tool_call["name"],
                    "input": arguments
                })

            messages.append({
                "role": "assistant",
                "content": content
            })

            # Anthropic format: all tool results in one user message
            tool_result_content = []
            for tool_call in response["tool_calls"]:
                tool_result_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call["id"],
                    "content": tool_results[tool_call["id"]]
                })
            messages.append({
                "role": "user",
                "content": tool_result_content
            })
        else:
            # OpenAI format: assistant message with tool_calls
            messages.append({
                "role": "assistant",
                "content": response.get("content") or "",
                "tool_calls": response["tool_calls"]
            })

            # OpenAI format: separate tool messages
            for tool_call in response["tool_calls"]:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": tool_results[tool_call["id"]]
                })

    def handle(self, query: str, context: "ConversationContext") -> str:
        """Handle a user query.

        Args:
            query: User's question
            context: Conversation context

        Returns:
            Answer to the query
        """
        messages = self._prepare_messages(query, context)
        tools = self._get_tools()

        # Agentic loop - allow up to 10 tool calls
        max_iterations = 10
        iteration = 0

        try:
            while iteration < max_iterations:
                response = self.llm.complete(messages, tools=tools, temperature=0.7)

                # Check if there are tool calls
                if "tool_calls" in response and response["tool_calls"]:
                    # Execute all tool calls and collect results
                    tool_results = {}
                    for tool_call in response["tool_calls"]:
                        tool_name = tool_call["name"]
                        try:
                            arguments = json.loads(tool_call["arguments"]) if isinstance(tool_call["arguments"], str) else tool_call["arguments"]
                        except json.JSONDecodeError:
                            arguments = {}

                        console.print(f"[dim]🔧 Using {tool_name}...[/dim]")

                        # Execute the tool
                        result = self._execute_tool(tool_name, arguments)
                        tool_results[tool_call["id"]] = result

                    # Add tool calls and results to messages
                    self._add_tool_results_to_messages(messages, response, tool_results)

                    iteration += 1
                    continue

                # No tool calls, we have our final answer
                return response["content"]

            # Max iterations reached
            return "I've gathered a lot of information but need to stop here. Based on what I found:\n\n" + response.get("content", "Unable to complete the analysis.")

        except Exception as e:
            return f"I encountered an error while processing your query: {str(e)}\n\nYou can try rephrasing or use /help to see available commands."

    def handle_stream(self, query: str, context: "ConversationContext") -> Generator[str, None, None]:
        """Handle a user query with streaming response.

        Args:
            query: User's question
            context: Conversation context

        Yields:
            Text chunks as they arrive
        """
        messages = self._prepare_messages(query, context)
        tools = self._get_tools()

        # Agentic loop - allow up to 10 tool calls
        max_iterations = 10
        iteration = 0

        try:
            while iteration < max_iterations:
                response = self.llm.complete(messages, tools=tools, temperature=0.7)

                # Check if there are tool calls
                if "tool_calls" in response and response["tool_calls"]:
                    # Execute all tool calls and collect results
                    tool_results = {}
                    for tool_call in response["tool_calls"]:
                        tool_name = tool_call["name"]
                        try:
                            arguments = json.loads(tool_call["arguments"]) if isinstance(tool_call["arguments"], str) else tool_call["arguments"]
                        except json.JSONDecodeError:
                            arguments = {}

                        console.print(f"[dim]🔧 Using {tool_name}...[/dim]")

                        # Execute the tool
                        result = self._execute_tool(tool_name, arguments)
                        tool_results[tool_call["id"]] = result

                    # Add tool calls and results to messages
                    self._add_tool_results_to_messages(messages, response, tool_results)

                    iteration += 1
                    continue

                # No tool calls, stream the final answer
                final_messages = messages + [{"role": "assistant", "content": response.get("content", "")}]
                # Re-run without tools to get streaming response
                yield from self.llm.stream(final_messages[:-1], temperature=0.7)
                return

            # Max iterations reached
            yield "I've gathered a lot of information but need to stop here. Based on what I found:\n\n"
            yield response.get("content", "Unable to complete the analysis.")

        except Exception as e:
            yield f"I encountered an error while processing your query: {str(e)}\n\nYou can try rephrasing or use /help to see available commands."

    def _prepare_messages(self, query: str, context: "ConversationContext") -> list[dict]:
        """Prepare messages for LLM.

        Args:
            query: User's question
            context: Conversation context

        Returns:
            List of message dicts
        """
        # Gather information about the project
        info_parts = []

        # Get file index summary
        index = self.graph.file_index.load_from_disk()
        if index:
            summary = index.summary
            total_files = summary.get("total_files", 0)
            total_mb = summary.get("total_size", 0) / (1024 * 1024)
            languages = summary.get("languages", {})

            info_parts.append(f"**Project Statistics:**")
            info_parts.append(f"- {total_files} files ({total_mb:.2f} MB)")
            if languages:
                lang_list = ", ".join(f"{lang} ({count})" for lang, count in languages.items())
                info_parts.append(f"- Languages: {lang_list}")

        # Get context documents
        context_docs = self.graph._load_context_docs()
        if context_docs:
            info_parts.append("\n**Project Context:**")
            for doc in context_docs[:2]:  # Limit to first 2 docs
                # Take first 500 chars of each doc
                info_parts.append(doc[:500] + "..." if len(doc) > 500 else doc)

        # Get recent context
        context_summary = context.get_context_summary()
        if context_summary and context_summary != "No recent context":
            info_parts.append(f"\n**Recent Activity:**\n{context_summary}")

        # Build prompt for LLM
        system_prompt = self._build_system_prompt("\n\n".join(info_parts))

        # Get conversation messages
        messages = context.to_messages()

        # Add current query if not already in messages
        if not messages or messages[-1]["content"] != query:
            messages.append({"role": "user", "content": query})

        # Update system prompt if needed
        if messages and messages[0]["role"] == "system":
            messages[0]["content"] = system_prompt
        else:
            messages.insert(0, {"role": "system", "content": system_prompt})

        return messages

    def _build_system_prompt(self, project_info: str) -> str:
        """Build system prompt for query handling.

        Args:
            project_info: Information about the project

        Returns:
            System prompt string
        """
        return f"""You are PitCrew, an AI coding assistant helping with this project.

{project_info}

Your role:
- Answer questions about the project clearly and concisely
- PROACTIVELY use the available tools to explore the codebase when answering questions
- Be thorough and investigate before answering
- IMPORTANT: Use get_file_summary instead of read_file for understanding code (saves context)

Available tools:
- list_files: List files in a directory (use "." for project root)
- get_file_summary: Get AI-generated summary of a file (USE THIS for understanding code)
- read_file: Read full file contents (only use when you need exact code)
- search_code: Search for code patterns

When asked about the project, follow this approach:
1. Use list_files to see the project structure
2. Use get_file_summary on key files (README, main files, config files)
3. Only use read_file if you need exact code or specific line details
4. Provide a comprehensive answer based on the summaries

Keep responses focused and practical. Prefer summaries over full file reads to conserve context."""
