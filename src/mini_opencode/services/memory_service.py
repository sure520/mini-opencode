"""Memory service for managing long-term memory using Mem0."""

import asyncio
from typing import Any

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from mini_opencode.config import get_config_section

logger = structlog.get_logger()


class MemoryService:
    """Service for managing long-term memory with Mem0.

    This service wraps the Mem0 Memory client to provide asynchronous
    memory operations for storing and retrieving conversation history,
    code modifications, and user preferences.
    """

    def __init__(self, enabled: bool = True, user_id: str = 'default') -> None:
        """Initialize the memory service.

        Args:
            enabled: Whether memory functionality is enabled.
            user_id: Unique identifier for the user.
        """
        self._enabled = enabled
        self._user_id = user_id
        self._memory: Any | None = None
        self._search_limit = 5

        if enabled:
            try:
                from mem0 import Memory

                # Load Mem0 configuration from config if available
                mem0_config = get_config_section(['memory', 'config'])
                if mem0_config and isinstance(mem0_config, dict):
                    self._memory = Memory.from_config(config_dict=mem0_config)
                else:
                    self._memory = Memory()

                # Load search limit from config
                limit = get_config_section(['memory', 'search_limit'])
                if isinstance(limit, int):
                    self._search_limit = limit

                logger.info('memory_service.initialized', user_id=user_id)
            except ImportError:
                logger.warning('mem0ai not installed, memory service disabled')
                self._enabled = False
            except Exception as e:
                logger.error('memory_service.init_failed', error=str(e))
                self._enabled = False

    @property
    def is_enabled(self) -> bool:
        """Check if memory service is enabled and initialized."""
        return self._enabled and self._memory is not None

    async def add_interaction(
        self,
        messages: list[dict[str, str]],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Save a conversation interaction to memory.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            metadata: Optional metadata to attach to the memory.

        Returns:
            The result from Mem0 add operation, or None if disabled.
        """
        if not self.is_enabled or not self._memory:
            return None

        try:
            # Run synchronous Mem0 operation in thread pool
            loop = asyncio.get_event_loop()
            mem = self._memory
            assert mem is not None  # Guaranteed by is_enabled check
            result = await loop.run_in_executor(
                None,
                lambda: mem.add(
                    messages=messages,
                    user_id=self._user_id,
                    metadata=metadata or {},
                ),
            )
            logger.debug(
                'memory_service.added_interaction',
                user_id=self._user_id,
                message_count=len(messages),
            )
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.error('memory_service.add_failed', error=str(e))
            return None

    async def add_messages(
        self,
        messages: list[BaseMessage],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Save LangChain messages to memory.

        Args:
            messages: List of LangChain message objects.
            metadata: Optional metadata to attach to the memory.

        Returns:
            The result from Mem0 add operation, or None if disabled.
        """
        if not self.is_enabled:
            return None

        # Convert LangChain messages to Mem0 format
        mem0_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                mem0_messages.append(
                    {'role': 'user', 'content': str(msg.content)}
                )
            elif isinstance(msg, AIMessage):
                mem0_messages.append(
                    {'role': 'assistant', 'content': str(msg.content)}
                )

        if mem0_messages:
            return await self.add_interaction(mem0_messages, metadata)
        return None

    async def search_relevant_memories(
        self,
        query: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search for relevant memories.

        Args:
            query: The search query.
            limit: Maximum number of results to return.

        Returns:
            List of relevant memory results.
        """
        if not self.is_enabled or not self._memory:
            return []

        try:
            limit = limit or self._search_limit
            loop = asyncio.get_event_loop()
            mem = self._memory
            assert mem is not None  # Guaranteed by is_enabled check
            result = await loop.run_in_executor(
                None,
                lambda: mem.search(
                    query=query,
                    user_id=self._user_id,
                    limit=limit,
                ),
            )
            memories = result.get('results', []) if isinstance(result, dict) else []
            logger.debug(
                'memory_service.searched',
                user_id=self._user_id,
                query=query,
                results_count=len(memories),
            )
            return memories
        except Exception as e:
            logger.error('memory_service.search_failed', error=str(e))
            return []

    def get_memory_context(
        self,
        query: str,
        limit: int | None = None,
    ) -> str:
        """Get formatted memory context for injection into prompts.

        Args:
            query: The search query.
            limit: Maximum number of memories to include.

        Returns:
            Formatted memory context string.
        """
        if not self.is_enabled:
            return ''

        # Use run_coroutine_threadsafe for synchronous context
        try:
            loop = asyncio.get_event_loop()
            memories = asyncio.run_coroutine_threadsafe(
                self.search_relevant_memories(query, limit),
                loop,
            ).result(timeout=5.0)
        except Exception:
            return ''

        if not memories:
            return ''

        memory_texts = []
        for mem in memories:
            memory_text = mem.get('memory', '')
            if memory_text:
                memory_texts.append(f"- {memory_text}")

        if not memory_texts:
            return ''

        return '\n'.join(['## Relevant Context from Past Interactions:'] + memory_texts)

    async def get_all_memories(self) -> list[dict[str, Any]]:
        """Get all memories for the current user.

        Returns:
            List of all memories.
        """
        if not self.is_enabled or not self._memory:
            return []

        try:
            loop = asyncio.get_event_loop()
            mem = self._memory
            assert mem is not None  # Guaranteed by is_enabled check
            result = await loop.run_in_executor(
                None,
                lambda: mem.get_all(user_id=self._user_id),
            )
            return result.get('results', []) if isinstance(result, dict) else []
        except Exception as e:
            logger.error('memory_service.get_all_failed', error=str(e))
            return []

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a specific memory.

        Args:
            memory_id: The ID of the memory to delete.

        Returns:
            True if deleted successfully, False otherwise.
        """
        if not self.is_enabled or not self._memory:
            return False

        try:
            loop = asyncio.get_event_loop()
            mem = self._memory
            assert mem is not None  # Guaranteed by is_enabled check
            await loop.run_in_executor(
                None,
                lambda: mem.delete(memory_id=memory_id),
            )
            logger.info('memory_service.deleted', memory_id=memory_id)
            return True
        except Exception as e:
            logger.error('memory_service.delete_failed', error=str(e))
            return False

    async def clear_all_memories(self) -> bool:
        """Clear all memories for the current user.

        Returns:
            True if cleared successfully, False otherwise.
        """
        if not self.is_enabled or not self._memory:
            return False

        try:
            loop = asyncio.get_event_loop()
            mem = self._memory
            assert mem is not None  # Guaranteed by is_enabled check
            await loop.run_in_executor(
                None,
                lambda: mem.delete_all(user_id=self._user_id),
            )
            logger.info('memory_service.cleared_all', user_id=self._user_id)
            return True
        except Exception as e:
            logger.error('memory_service.clear_failed', error=str(e))
            return False

    def update_user_id(self, user_id: str) -> None:
        """Update the user ID for memory isolation.

        Args:
            user_id: The new user ID.
        """
        self._user_id = user_id
        logger.info('memory_service.user_id_updated', user_id=user_id)
