"""Query handler for answering questions about the project."""

from typing import TYPE_CHECKING, Generator

from pitcrew.llm import LLM

if TYPE_CHECKING:
    from pitcrew.conversation import ConversationContext
    from pitcrew.graph import PitCrewGraph


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

    def handle(self, query: str, context: "ConversationContext") -> str:
        """Handle a user query.

        Args:
            query: User's question
            context: Conversation context

        Returns:
            Answer to the query
        """
        messages = self._prepare_messages(query, context)

        try:
            response = self.llm.complete(messages, temperature=0.7)
            return response["content"]
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

        try:
            yield from self.llm.stream(messages, temperature=0.7)
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
- Suggest using /read <file> if you need to see specific code
- Recommend /plan if the user wants to make changes
- Be helpful and conversational

Keep responses focused and practical. If you don't have enough information, say so and suggest next steps."""
