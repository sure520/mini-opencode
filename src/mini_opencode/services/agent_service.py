"""Agent service for handling agent-related business logic."""

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import MessagesState

from mini_opencode.services.memory_service import MemoryService


class AgentService:
    """Service for managing agent business logic with memory support."""

    def __init__(self, memory_service: MemoryService | None = None) -> None:
        """Initialize the agent service.

        Args:
            memory_service: Optional memory service for long-term memory.
        """
        self._memory_service = memory_service

    @property
    def memory_service(self) -> MemoryService | None:
        """Get the memory service."""
        return self._memory_service

    def set_memory_service(self, memory_service: MemoryService) -> None:
        """Set the memory service.

        Args:
            memory_service: The memory service to use.
        """
        self._memory_service = memory_service

    def process_user_input(
        self, input_text: str, state: MessagesState
    ) -> dict[str, Any]:
        """Process user input and generate agent response.

        Args:
            input_text: The user input text.
            state: The current agent state.

        Returns:
            Dict: Processed input and state updates.
        """
        # This will be implemented with actual agent logic
        return {'input': input_text, 'state': state}

    def generate_agent_response(self, messages: list[BaseMessage]) -> str:
        """Generate agent response based on messages.

        Args:
            messages: List of messages in the conversation.

        Returns:
            str: Agent response.
        """
        # This will be implemented with actual agent logic
        return 'Processing your request...'

    def validate_agent_state(self, state: MessagesState) -> bool:
        """Validate the agent state.

        Args:
            state: The agent state to validate.

        Returns:
            bool: True if state is valid, False otherwise.
        """
        return hasattr(state, 'messages')

    async def save_conversation_to_memory(
        self,
        user_message: HumanMessage,
        ai_message: AIMessage,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Save a conversation interaction to long-term memory.

        Args:
            user_message: The user's message.
            ai_message: The AI's response.
            metadata: Optional metadata about the interaction.

        Returns:
            The result from memory storage, or None if memory is disabled.
        """
        if self._memory_service is None or not self._memory_service.is_enabled:
            return None

        return await self._memory_service.add_messages(
            [user_message, ai_message],
            metadata=metadata,
        )

    async def get_relevant_memories(
        self, query: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Get relevant memories for a query.

        Args:
            query: The search query.
            limit: Maximum number of results.

        Returns:
            List of relevant memories.
        """
        if self._memory_service is None or not self._memory_service.is_enabled:
            return []

        return await self._memory_service.search_relevant_memories(query, limit)

    def get_memory_context(self, query: str) -> str:
        """Get formatted memory context for prompt injection.

        Args:
            query: The search query.

        Returns:
            Formatted memory context string.
        """
        if self._memory_service is None:
            return ''

        return self._memory_service.get_memory_context(query)
