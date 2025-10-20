"""System prompt builder with Anthropic prompt caching support."""

from pathlib import Path
from typing import Optional


class SystemPromptBuilder:
    """Builds comprehensive system prompts with caching support for Anthropic."""

    def __init__(self, project_root: Path, agents_md_content: Optional[str] = None):
        """Initialize system prompt builder.

        Args:
            project_root: Project root directory
            agents_md_content: Optional pre-loaded AGENTS.md content
        """
        self.project_root = project_root
        self.agents_md_content = agents_md_content

    def build_system_messages(self) -> list[dict]:
        """Build system messages with cache_control for Anthropic.

        Returns structured messages with cache breakpoints for optimal performance.
        Anthropic caches the last 4 blocks marked with cache_control.

        Returns:
            List of system message blocks with cache_control markers
        """
        messages = []

        # Block 1: Core identity and role (rarely changes, cache it)
        core_identity = self._build_core_identity()
        messages.append({
            "type": "text",
            "text": core_identity,
            "cache_control": {"type": "ephemeral"}
        })

        # Block 2: Coding guidelines and best practices (rarely changes, cache it)
        coding_guidelines = self._build_coding_guidelines()
        messages.append({
            "type": "text",
            "text": coding_guidelines,
            "cache_control": {"type": "ephemeral"}
        })

        # Block 3: Chain-of-thought instructions (rarely changes, cache it)
        cot_instructions = self._build_cot_instructions()
        messages.append({
            "type": "text",
            "text": cot_instructions,
            "cache_control": {"type": "ephemeral"}
        })

        # Block 4: Project context from AGENTS.md (changes per project, cache it)
        if self.agents_md_content:
            project_context = self._build_project_context()
            messages.append({
                "type": "text",
                "text": project_context,
                "cache_control": {"type": "ephemeral"}
            })

        return messages

    def _build_core_identity(self) -> str:
        """Build core identity and role description."""
        return """# PitCrew AI Coding Assistant

You are PitCrew, an expert AI coding assistant built on Claude. Your role is to help developers:

## Core Responsibilities
- **Understand codebases**: Read and analyze code to answer questions
- **Plan changes**: Generate structured, multi-file edit plans
- **Implement code**: Write complete, working implementations (not stubs or TODOs)
- **Debug issues**: Analyze errors and automatically fix problems
- **Run tests**: Execute and validate changes

## Operating Principles
1. **Action-oriented**: You take concrete actions, not just suggestions
2. **Complete implementations**: Always write full, working code - never placeholders
3. **Safety-first**: Confirm before making destructive changes
4. **Context-aware**: Use project conventions and patterns
5. **Transparent**: Show your reasoning process
6. **Iterative**: Fix errors automatically, learn from failures

## Communication Style
- Concise and direct
- Technical and precise
- Show confidence in your decisions
- Explain reasoning when it matters
"""

    def _build_coding_guidelines(self) -> str:
        """Build coding standards and best practices."""
        return """# Coding Standards

## Code Organization
- **Use classes** for stateful logic and related functionality
- **Use functions** for stateless operations and utilities
- **Group related code** into modules with clear responsibilities
- **Follow language conventions**: PEP 8 for Python, etc.

## Implementation Quality
- Write **complete, working code** - no TODO comments or placeholders
- Include **proper error handling** with try/except blocks
- Add **type hints** where applicable (Python 3.6+)
- Write **docstrings** for classes and public methods
- Use **descriptive variable names** that explain intent
- Keep functions **focused and small** (single responsibility)

## Project Structure
- Place code in appropriate directories (src/, lib/, tests/)
- Name files based on their primary class/module
- Keep configuration in config/ or root-level files
- Put tests alongside or in tests/ directory

## Dependencies
- Import only what you need
- Use standard library when possible
- Clearly document external dependencies
- Handle missing imports gracefully

## Testing
- Write tests for new functionality
- Use descriptive test names that explain what's being tested
- Include edge cases and error conditions
- Use pytest for Python, appropriate frameworks for other languages
"""

    def _build_cot_instructions(self) -> str:
        """Build chain-of-thought instructions."""
        return """# Chain-of-Thought Process

When generating code or solving problems, ALWAYS use this structured thinking process:

## Format
Use XML-style tags to separate thinking from output:

```
<thinking>
[Your step-by-step reasoning here]
</thinking>

<code>
[The actual code or solution]
</code>
```

## Thinking Process
Your <thinking> section should address:

1. **Purpose**: What is this code supposed to do?
2. **Components**: What classes, functions, or modules are needed?
3. **Dependencies**: What imports and external libraries are required?
4. **Integration**: How does this fit with existing code?
5. **Edge cases**: What error handling or special cases are needed?
6. **Architecture**: What design patterns or approaches should be used?

## When Fixing Errors
For debugging, think about:

1. **Error type**: ImportError, SyntaxError, TypeError, logic error?
2. **Root cause**: What is the actual problem (not just symptoms)?
3. **Affected files**: Which specific files need changes?
4. **Solution**: What exact changes will fix this?
5. **Prevention**: How to avoid similar issues?

## Keep Thinking Focused
- Be specific, not generic
- Reference actual code and file names
- Identify concrete steps
- Explain non-obvious decisions
"""

    def _build_project_context(self) -> str:
        """Build project-specific context from AGENTS.md."""
        if not self.agents_md_content:
            return ""

        return f"""# Current Project Context

The following is comprehensive documentation about the current project you're working on.
Use this information to understand the codebase structure, conventions, and patterns.

{self.agents_md_content}

---

**Remember**: This project context should guide all your code generation, planning, and debugging decisions.
Follow the patterns and conventions documented above.
"""

    def build_simple_system_prompt(self) -> str:
        """Build a simple string-based system prompt (legacy compatibility).

        Returns:
            Single string system prompt
        """
        parts = [
            self._build_core_identity(),
            self._build_coding_guidelines(),
            self._build_cot_instructions(),
        ]

        if self.agents_md_content:
            parts.append(self._build_project_context())

        return "\n\n".join(parts)
