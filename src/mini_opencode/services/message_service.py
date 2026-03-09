"""Message service for handling message-related operations."""

from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage


class MessageService:
    """Service for managing message processing and storage."""

    def __init__(self):
        """Initialize the message service."""
        pass

    def create_human_message(self, content: str) -> HumanMessage:
        """Create a human message.

        Args:
            content: The message content.

        Returns:
            HumanMessage: The created human message.
        """
        return HumanMessage(content=content)

    def create_ai_message(self, content: str) -> AIMessage:
        """Create an AI message.

        Args:
            content: The message content.

        Returns:
            AIMessage: The created AI message.
        """
        return AIMessage(content=content)

    def create_system_message(self, content: str) -> SystemMessage:
        """Create a system message.

        Args:
            content: The message content.

        Returns:
            SystemMessage: The created system message.
        """
        return SystemMessage(content=content)

    def format_message_history(self, messages: List[BaseMessage]) -> str:
        """Format message history for display.

        Args:
            messages: List of messages.

        Returns:
            str: Formatted message history.
        """
        formatted = []
        for message in messages:
            if isinstance(message, HumanMessage):
                formatted.append(f"Human: {message.content}")
            elif isinstance(message, AIMessage):
                formatted.append(f"AI: {message.content}")
            elif isinstance(message, SystemMessage):
                formatted.append(f"System: {message.content}")
            else:
                formatted.append(f"{type(message).__name__}: {message.content}")
        return "\n".join(formatted)

    def extract_code_blocks(self, content: str) -> List[str]:
        """Extract code blocks from message content.

        Args:
            content: The message content.

        Returns:
            List[str]: List of code blocks found in the content.
        """
        import re
        code_blocks = re.findall(r"```(?:\w+)?\n(.*?)\n```", content, re.DOTALL)
        return code_blocks

    def validate_message(self, message: BaseMessage) -> bool:
        """Validate a message.

        Args:
            message: The message to validate.

        Returns:
            bool: True if message is valid, False otherwise.
        """
        return isinstance(message, BaseMessage) and hasattr(message, "content")
