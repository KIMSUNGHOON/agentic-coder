"""Conversation History Manager for Agentic 2.0

Manages conversation history with context window optimization for GPT-OSS-120B.

Key Features:
- Token-based context window management (4096 tokens for GPT-OSS-120B)
- Automatic message trimming to fit context window
- Shared context across agents
- Conversation persistence (optional)

Architecture:
┌─────────────────────────────────────────────────────────┐
│          ConversationHistory                            │
│  ┌──────────────────────────────────────────────────┐  │
│  │  System Prompt (always kept)                      │  │
│  ├──────────────────────────────────────────────────┤  │
│  │  [Old messages - trimmed if needed]               │  │
│  ├──────────────────────────────────────────────────┤  │
│  │  Recent messages (always kept)                    │  │
│  ├──────────────────────────────────────────────────┤  │
│  │  Current user message (always kept)               │  │
│  └──────────────────────────────────────────────────┘  │
│  Total: ≤ 3072 tokens (reserve 1024 for response)      │
└─────────────────────────────────────────────────────────┘
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Single message in conversation"""
    role: str  # "system", "user", "assistant"
    content: str
    timestamp: float
    tokens: int = 0  # Estimated token count


@dataclass
class SharedContext:
    """Context shared across agents and iterations"""
    completed_steps: List[str] = field(default_factory=list)
    plan: Dict[str, Any] = field(default_factory=dict)
    workspace: Optional[str] = None
    domain: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationHistory:
    """Manage conversation history with context window optimization

    This class handles:
    1. Conversation history storage
    2. Context window management (GPT-OSS-120B: 4096 tokens)
    3. Automatic message trimming
    4. Shared context across agents
    5. Token counting and optimization

    Example:
        >>> history = ConversationHistory(max_context_tokens=3072)
        >>> history.add_message("user", "Create a calculator in Python")
        >>> history.add_message("assistant", "I'll create a calculator...")
        >>> messages = history.get_messages_for_llm()
    """

    # GPT-OSS-120B context window size
    CONTEXT_WINDOW_SIZE = 4096
    # Reserve tokens for response
    RESERVED_FOR_RESPONSE = 1024
    # Maximum prompt size
    MAX_PROMPT_TOKENS = CONTEXT_WINDOW_SIZE - RESERVED_FOR_RESPONSE  # 3072

    def __init__(
        self,
        max_context_tokens: int = MAX_PROMPT_TOKENS,
        system_prompt: Optional[str] = None,
    ):
        """Initialize ConversationHistory

        Args:
            max_context_tokens: Maximum tokens for context (default: 3072)
            system_prompt: Optional system prompt (always kept)
        """
        self.max_context_tokens = max_context_tokens
        self.messages: List[Message] = []
        self.shared_context = SharedContext()

        # Add system prompt if provided
        if system_prompt:
            self.set_system_prompt(system_prompt)

        logger.info(
            f"📝 ConversationHistory initialized "
            f"(max_tokens: {max_context_tokens})"
        )

    def set_system_prompt(self, prompt: str) -> None:
        """Set or update system prompt (always kept in context)

        Args:
            prompt: System prompt text
        """
        tokens = self._estimate_tokens(prompt)

        # Remove existing system prompt
        self.messages = [m for m in self.messages if m.role != "system"]

        # Add new system prompt at the beginning
        import time
        self.messages.insert(0, Message(
            role="system",
            content=prompt,
            timestamp=time.time(),
            tokens=tokens
        ))

        logger.debug(f"📋 System prompt set ({tokens} tokens)")

    def add_message(
        self,
        role: str,
        content: str,
        auto_trim: bool = True
    ) -> None:
        """Add message to conversation history

        Args:
            role: Message role ("user", "assistant", "system")
            content: Message content
            auto_trim: Automatically trim old messages if needed (default: True)
        """
        import time

        tokens = self._estimate_tokens(content)

        message = Message(
            role=role,
            content=content,
            timestamp=time.time(),
            tokens=tokens
        )

        self.messages.append(message)

        logger.debug(f"💬 Added {role} message ({tokens} tokens)")

        # Auto-trim if enabled and over limit
        if auto_trim:
            total_tokens = self._count_total_tokens()
            if total_tokens > self.max_context_tokens:
                self._trim_to_context_window()

    def get_messages_for_llm(
        self,
        include_shared_context: bool = True
    ) -> List[Dict[str, str]]:
        """Get messages formatted for LLM API call

        Args:
            include_shared_context: Include shared context in system prompt (default: True)

        Returns:
            List of message dicts with 'role' and 'content'
        """
        messages = []

        for msg in self.messages:
            message_dict = {
                "role": msg.role,
                "content": msg.content
            }

            # Inject shared context into system prompt if requested
            if msg.role == "system" and include_shared_context:
                context_str = self._format_shared_context()
                if context_str:
                    message_dict["content"] = f"{msg.content}\n\n{context_str}"

            messages.append(message_dict)

        return messages

    def _format_shared_context(self) -> str:
        """Format shared context for injection into system prompt

        Returns:
            Formatted context string
        """
        parts = []

        # Add completed steps
        if self.shared_context.completed_steps:
            steps = ", ".join(self.shared_context.completed_steps[:10])
            parts.append(f"<completed_steps>{steps}</completed_steps>")

        # Add plan if available
        if self.shared_context.plan:
            plan_str = json.dumps(self.shared_context.plan, indent=2)
            # Limit plan size
            if len(plan_str) > 500:
                plan_str = plan_str[:500] + "..."
            parts.append(f"<plan>{plan_str}</plan>")

        # Add workspace
        if self.shared_context.workspace:
            parts.append(f"<workspace>{self.shared_context.workspace}</workspace>")

        # Add domain
        if self.shared_context.domain:
            parts.append(f"<domain>{self.shared_context.domain}</domain>")

        if parts:
            return "<context>\n" + "\n".join(parts) + "\n</context>"
        return ""

    def _trim_to_context_window(self) -> None:
        """Trim old messages to fit within context window

        Strategy:
        1. Always keep system prompt (index 0)
        2. Always keep last user message
        3. Always keep last assistant message
        4. Trim old messages from the middle
        """
        # Find indices
        system_msg = None
        last_user_idx = None
        last_assistant_idx = None

        for i, msg in enumerate(self.messages):
            if msg.role == "system":
                system_msg = i
            elif msg.role == "user":
                last_user_idx = i
            elif msg.role == "assistant":
                last_assistant_idx = i

        # Messages to always keep
        keep_indices = set()
        if system_msg is not None:
            keep_indices.add(system_msg)
        if last_user_idx is not None:
            keep_indices.add(last_user_idx)
        if last_assistant_idx is not None:
            keep_indices.add(last_assistant_idx)

        # Try removing messages from oldest to newest (skip kept messages)
        current_tokens = self._count_total_tokens()

        i = 0
        while current_tokens > self.max_context_tokens and i < len(self.messages):
            if i not in keep_indices:
                removed_msg = self.messages.pop(i)
                current_tokens -= removed_msg.tokens
                logger.debug(
                    f"🗑️  Trimmed {removed_msg.role} message "
                    f"({removed_msg.tokens} tokens)"
                )
            else:
                i += 1

        final_tokens = self._count_total_tokens()
        logger.info(
            f"✂️  Trimmed conversation: {final_tokens}/{self.max_context_tokens} tokens"
        )

    def _count_total_tokens(self) -> int:
        """Count total tokens in conversation

        Returns:
            Total token count
        """
        return sum(msg.tokens for msg in self.messages)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text

        Uses simple heuristic: ~4 characters per token
        This is approximate but sufficient for context management.

        For more accurate counting, could use tiktoken library.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # Simple heuristic: 4 chars ≈ 1 token
        # Add some padding for JSON formatting, etc.
        return int(len(text) / 4 * 1.2)

    def clear(self, keep_system_prompt: bool = True) -> None:
        """Clear conversation history

        Args:
            keep_system_prompt: Keep system prompt (default: True)
        """
        if keep_system_prompt:
            system_msgs = [m for m in self.messages if m.role == "system"]
            self.messages = system_msgs
        else:
            self.messages = []

        logger.info("🗑️  Conversation history cleared")

    def get_context(self, key: str) -> Any:
        """Get value from shared context

        Args:
            key: Context key

        Returns:
            Context value or None
        """
        if hasattr(self.shared_context, key):
            return getattr(self.shared_context, key)
        return self.shared_context.metadata.get(key)

    def set_context(self, key: str, value: Any) -> None:
        """Set value in shared context

        Args:
            key: Context key
            value: Context value
        """
        # Try to set on SharedContext fields first
        if hasattr(self.shared_context, key):
            setattr(self.shared_context, key, value)
        else:
            # Otherwise, use metadata
            self.shared_context.metadata[key] = value

        logger.debug(f"📌 Context set: {key}")

    def add_completed_step(self, step: str) -> None:
        """Add completed step to shared context

        Args:
            step: Step description
        """
        self.shared_context.completed_steps.append(step)
        logger.debug(f"✅ Completed step: {step}")

    def get_stats(self) -> Dict[str, Any]:
        """Get conversation statistics

        Returns:
            Dictionary with statistics
        """
        total_tokens = self._count_total_tokens()
        message_counts = {}

        for msg in self.messages:
            message_counts[msg.role] = message_counts.get(msg.role, 0) + 1

        return {
            "total_messages": len(self.messages),
            "total_tokens": total_tokens,
            "max_tokens": self.max_context_tokens,
            "usage_percent": (total_tokens / self.max_context_tokens * 100),
            "message_counts": message_counts,
            "completed_steps": len(self.shared_context.completed_steps),
        }

    def __repr__(self) -> str:
        """String representation"""
        stats = self.get_stats()
        return (
            f"ConversationHistory("
            f"messages={stats['total_messages']}, "
            f"tokens={stats['total_tokens']}/{stats['max_tokens']}, "
            f"usage={stats['usage_percent']:.1f}%)"
        )


# Default system prompt for Agentic 2.0
DEFAULT_SYSTEM_PROMPT = """You are Agentic 2.0, an advanced AI coding assistant.

Your capabilities:
- Code generation and modification
- Bug fixing and debugging
- Research and analysis
- Data processing and visualization
- General task assistance

Important guidelines:
- Always provide clear, concise responses
- Use the shared context to maintain consistency
- Reference completed steps when building on previous work
- Ask for clarification if requirements are unclear
- Prioritize correctness and best practices

You have access to tools for file operations, command execution, and more.
Use them responsibly and safely.
"""


def create_conversation_history(
    system_prompt: Optional[str] = None,
    max_tokens: int = ConversationHistory.MAX_PROMPT_TOKENS,
) -> ConversationHistory:
    """Create a new conversation history instance

    Args:
        system_prompt: Optional system prompt (uses default if not provided)
        max_tokens: Maximum context tokens (default: 3072)

    Returns:
        ConversationHistory instance
    """
    if system_prompt is None:
        system_prompt = DEFAULT_SYSTEM_PROMPT

    return ConversationHistory(
        max_context_tokens=max_tokens,
        system_prompt=system_prompt
    )
