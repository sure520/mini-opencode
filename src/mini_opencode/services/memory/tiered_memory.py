"""Tiered memory manager for the hierarchical memory system.

This module provides the TieredMemoryManager which integrates:
- Short-term Memory: Session messages (in-memory storage)
- Working Memory: Task contexts (in-memory with TTL)
- Long-term Memory: Permanent storage (Mem0 backend)
"""

import asyncio
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

import structlog

from .decay import DecayCalculator, calculate_relevance_score
from .importance import FeedbackSignal, ImportanceMetrics, ImportanceScorer
from .types import (
    CATEGORY_IMPORTANCE_SCORES,
    LongTermMemory,
    Memory,
    MemoryCategory,
    MemorySearchResult,
    MemoryTier,
    ShortTermMemory,
    TieredMemoryConfig,
    WorkingMemory,
)

logger = structlog.get_logger()


class ShortTermStore:
    """In-memory store for short-term session messages.

    Uses an LRU-like structure to maintain capacity limits.
    """

    def __init__(self, capacity: int = 100) -> None:
        """Initialize the short-term store.

        Args:
            capacity: Maximum number of messages to store.
        """
        self.capacity = capacity
        self._messages: OrderedDict[str, ShortTermMemory] = OrderedDict()
        self._session_id: str = ""

    def set_session(self, session_id: str) -> None:
        """Set the current session ID."""
        self._session_id = session_id

    def add(self, content: str, metadata: dict[str, Any] | None = None) -> ShortTermMemory:
        """Add a message to short-term memory.

        Args:
            content: The message content.
            metadata: Optional metadata.

        Returns:
            The created ShortTermMemory.
        """
        memory_id = str(uuid.uuid4())
        message_index = len(self._messages)

        memory = ShortTermMemory(
            id=memory_id,
            content=content,
            tier=MemoryTier.SHORT_TERM,
            session_id=self._session_id,
            message_index=message_index,
            metadata=metadata or {},
        )

        # Enforce capacity limit (LRU eviction)
        while len(self._messages) >= self.capacity:
            self._messages.popitem(last=False)

        self._messages[memory_id] = memory
        return memory

    def get(self, memory_id: str) -> ShortTermMemory | None:
        """Get a message by ID."""
        memory = self._messages.get(memory_id)
        if memory:
            memory.update_access()
            # Move to end (most recently accessed)
            self._messages.move_to_end(memory_id)
        return memory

    def get_recent(self, n: int = 10) -> list[ShortTermMemory]:
        """Get the N most recent messages."""
        items = list(self._messages.values())
        return items[-n:] if len(items) > n else items

    def get_all(self) -> list[ShortTermMemory]:
        """Get all messages in order."""
        return list(self._messages.values())

    def clear(self) -> None:
        """Clear all short-term memory."""
        self._messages.clear()

    def __len__(self) -> int:
        """Return number of stored messages."""
        return len(self._messages)


class WorkingStore:
    """In-memory store for working memory (task contexts).

    Automatically expires entries based on TTL.
    """

    def __init__(self, capacity: int = 10, ttl_hours: int = 24) -> None:
        """Initialize the working store.

        Args:
            capacity: Maximum number of task contexts.
            ttl_hours: Time-to-live in hours.
        """
        self.capacity = capacity
        self.ttl_hours = ttl_hours
        self._contexts: dict[str, WorkingMemory] = {}

    def add(
        self,
        task_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> WorkingMemory:
        """Add or update a task context.

        Args:
            task_id: The task identifier.
            content: The context content.
            metadata: Optional metadata.

        Returns:
            The created or updated WorkingMemory.
        """
        memory_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=self.ttl_hours)

        memory = WorkingMemory(
            id=memory_id,
            content=content,
            tier=MemoryTier.WORKING,
            task_id=task_id,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        # Remove expired entries
        self._cleanup_expired()

        # Enforce capacity (remove oldest)
        while len(self._contexts) >= self.capacity:
            oldest_id = min(self._contexts.keys(), key=lambda k: self._contexts[k].created_at)
            del self._contexts[oldest_id]

        self._contexts[memory_id] = memory
        return memory

    def get(self, memory_id: str) -> WorkingMemory | None:
        """Get a context by ID."""
        self._cleanup_expired()
        memory = self._contexts.get(memory_id)
        if memory:
            memory.update_access()
        return memory

    def get_by_task(self, task_id: str) -> list[WorkingMemory]:
        """Get all contexts for a task."""
        self._cleanup_expired()
        return [m for m in self._contexts.values() if m.task_id == task_id]

    def get_active(self) -> list[WorkingMemory]:
        """Get all active (non-expired) contexts."""
        self._cleanup_expired()
        return list(self._contexts.values())

    def extend_ttl(self, memory_id: str, hours: int | None = None) -> bool:
        """Extend the TTL of a context.

        Args:
            memory_id: The memory to extend.
            hours: Hours to extend by. Defaults to ttl_hours.

        Returns:
            True if extended, False if not found.
        """
        memory = self._contexts.get(memory_id)
        if memory:
            extension = hours or self.ttl_hours
            memory.expires_at = datetime.now() + timedelta(hours=extension)
            return True
        return False

    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        now = datetime.now()
        expired_ids = [mid for mid, m in self._contexts.items() if m.is_expired(now)]
        for mid in expired_ids:
            del self._contexts[mid]

    def clear(self) -> None:
        """Clear all working memory."""
        self._contexts.clear()

    def __len__(self) -> int:
        """Return number of active contexts."""
        self._cleanup_expired()
        return len(self._contexts)


class TieredMemoryManager:
    """Manager for the three-tier memory system.

    This class orchestrates short-term, working, and long-term memory
    to provide a unified interface for memory operations.
    """

    def __init__(
        self,
        config: TieredMemoryConfig | None = None,
        user_id: str = "default",
        mem0_enabled: bool = True,
    ) -> None:
        """Initialize the tiered memory manager.

        Args:
            config: Configuration for the memory system.
            user_id: User identifier for memory isolation.
            mem0_enabled: Whether to enable Mem0 long-term memory.
        """
        self.config = config or TieredMemoryConfig()
        self.user_id = user_id

        # Initialize stores
        self.short_term = ShortTermStore(capacity=self.config.short_term_capacity)
        self.working = WorkingStore(
            capacity=self.config.working_memory_capacity,
            ttl_hours=self.config.working_memory_ttl_hours,
        )

        # Initialize calculators
        self.decay_calculator = DecayCalculator(
            half_life_days=self.config.decay_half_life_days,
            min_decay=self.config.min_decay_factor,
        )
        self.importance_scorer = ImportanceScorer()

        # Long-term memory (Mem0)
        self._mem0_enabled = mem0_enabled
        self._mem0: Any = None
        if mem0_enabled:
            self._init_mem0()

        # Importance metrics cache
        self._importance_cache: dict[str, ImportanceMetrics] = {}

        logger.info(
            "tiered_memory.initialized",
            user_id=user_id,
            mem0_enabled=mem0_enabled,
            short_term_capacity=self.config.short_term_capacity,
            working_memory_capacity=self.config.working_memory_capacity,
        )

    def _init_mem0(self) -> None:
        """Initialize Mem0 client."""
        try:
            from mem0 import Memory

            from mini_opencode.config import get_config_section

            mem0_config = get_config_section(["memory", "config"])
            if mem0_config and isinstance(mem0_config, dict):
                self._mem0 = Memory.from_config(config_dict=mem0_config)
            else:
                self._mem0 = Memory()
        except ImportError:
            logger.warning("mem0ai not installed, long-term memory disabled")
            self._mem0_enabled = False
        except Exception as e:
            logger.error("tiered_memory.mem0_init_failed", error=str(e))
            self._mem0_enabled = False

    @property
    def is_mem0_enabled(self) -> bool:
        """Check if Mem0 long-term memory is available."""
        return self._mem0_enabled and self._mem0 is not None

    # ==================== Short-term Memory Operations ====================

    def add_message(
        self,
        content: str,
        category: MemoryCategory | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ShortTermMemory:
        """Add a message to short-term memory.

        Args:
            content: The message content.
            category: Optional category for importance scoring.
            metadata: Optional metadata.

        Returns:
            The created ShortTermMemory.
        """
        memory = self.short_term.add(content, metadata)

        # Initialize importance metrics
        if category:
            memory.category = category
        else:
            memory.category = self.importance_scorer._detect_category(content)

        memory.importance_score = self.importance_scorer.calculate_initial_score(content, memory.category)

        self._importance_cache[memory.id] = ImportanceMetrics(base_score=memory.importance_score)

        return memory

    def get_recent_messages(self, n: int = 10) -> list[ShortTermMemory]:
        """Get recent messages from short-term memory."""
        return self.short_term.get_recent(n)

    # ==================== Working Memory Operations ====================

    def add_task_context(
        self,
        task_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> WorkingMemory:
        """Add a task context to working memory.

        Args:
            task_id: The task identifier.
            content: The context content.
            metadata: Optional metadata.

        Returns:
            The created WorkingMemory.
        """
        memory = self.working.add(task_id, content, metadata)
        memory.category = MemoryCategory.TASK
        memory.importance_score = CATEGORY_IMPORTANCE_SCORES[MemoryCategory.TASK]
        return memory

    def get_task_context(self, task_id: str) -> list[WorkingMemory]:
        """Get all context for a specific task."""
        return self.working.get_by_task(task_id)

    def get_active_contexts(self) -> list[WorkingMemory]:
        """Get all active working memory contexts."""
        return self.working.get_active()

    # ==================== Long-term Memory Operations ====================

    async def add_to_long_term(
        self,
        content: str,
        category: MemoryCategory | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LongTermMemory | None:
        """Add content to long-term memory (Mem0).

        Args:
            content: The content to store.
            category: The content category.
            metadata: Optional metadata.

        Returns:
            The created LongTermMemory, or None if Mem0 is disabled.
        """
        if not self.is_mem0_enabled:
            return None

        memory_id = str(uuid.uuid4())
        detected_category = category or self.importance_scorer._detect_category(content)
        importance = self.importance_scorer.calculate_initial_score(content, detected_category)

        try:
            # Store in Mem0
            loop = asyncio.get_event_loop()
            mem = self._mem0
            assert mem is not None

            mem0_metadata = {
                "category": detected_category.value,
                "importance": importance,
                "internal_id": memory_id,
                **(metadata or {}),
            }

            result = await loop.run_in_executor(
                None,
                lambda: mem.add(
                    messages=[{"role": "user", "content": content}],
                    user_id=self.user_id,
                    metadata=mem0_metadata,
                ),
            )

            # Create LongTermMemory object
            mem0_id = ""
            if isinstance(result, dict) and "results" in result:
                results = result.get("results", [])
                if results:
                    mem0_id = results[0].get("id", "")

            memory = LongTermMemory(
                id=memory_id,
                content=content,
                tier=MemoryTier.LONG_TERM,
                category=detected_category,
                importance_score=importance,
                mem0_id=mem0_id,
                metadata=metadata or {},
            )

            logger.debug("tiered_memory.added_long_term", memory_id=memory_id, mem0_id=mem0_id)
            return memory

        except Exception as e:
            logger.error("tiered_memory.add_long_term_failed", error=str(e))
            return None

    async def search_long_term(
        self,
        query: str,
        limit: int | None = None,
    ) -> list[MemorySearchResult]:
        """Search long-term memory with relevance scoring.

        Args:
            query: The search query.
            limit: Maximum results to return.

        Returns:
            List of MemorySearchResult sorted by relevance.
        """
        if not self.is_mem0_enabled:
            return []

        limit = limit or self.config.long_term_search_limit

        try:
            loop = asyncio.get_event_loop()
            mem = self._mem0
            assert mem is not None

            raw_results = await loop.run_in_executor(
                None,
                lambda: mem.search(query=query, user_id=self.user_id, limit=limit * 2),  # Get more for re-ranking
            )

            memories = raw_results.get("results", []) if isinstance(raw_results, dict) else []

            # Convert to MemorySearchResult with relevance scoring
            results = []
            now = datetime.now()

            for mem_data in memories:
                # Extract memory info
                content = mem_data.get("memory", "")
                metadata = mem_data.get("metadata", {})
                created_str = mem_data.get("created_at", "")

                # Parse created_at
                try:
                    created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    created_at = now

                # Get or calculate importance
                importance = metadata.get("importance", 0.3)
                if isinstance(importance, str):
                    importance = float(importance)

                # Calculate decay
                decay = self.decay_calculator.calculate_decay(created_at, now)

                # Similarity score from Mem0 (if available)
                similarity = mem_data.get("score", 0.7)

                # Create Memory object
                memory = LongTermMemory(
                    id=metadata.get("internal_id", mem_data.get("id", "")),
                    content=content,
                    tier=MemoryTier.LONG_TERM,
                    category=MemoryCategory(metadata.get("category", "conversation")),
                    created_at=created_at,
                    importance_score=importance,
                    mem0_id=mem_data.get("id", ""),
                    decay_factor=decay,
                )

                # Calculate relevance
                relevance = calculate_relevance_score(
                    similarity=similarity,
                    decay_factor=decay,
                    importance=importance,
                )

                results.append(
                    MemorySearchResult(
                        memory=memory,
                        similarity_score=similarity,
                        decay_factor=decay,
                        relevance_score=relevance,
                    )
                )

            # Sort by relevance and limit
            results.sort(key=lambda r: r.relevance_score, reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error("tiered_memory.search_failed", error=str(e))
            return []

    # ==================== Unified Operations ====================

    async def search_all_tiers(
        self,
        query: str,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        """Search across all memory tiers.

        Short-term and working memory use simple text matching.
        Long-term memory uses semantic search.

        Args:
            query: The search query.
            limit: Maximum total results.

        Returns:
            Combined and sorted MemorySearchResult list.
        """
        results: list[MemorySearchResult] = []
        query_lower = query.lower()

        # Search short-term (simple text match)
        for mem in self.short_term.get_all():
            if query_lower in mem.content.lower():
                decay = self.decay_calculator.calculate_decay(mem.created_at)
                similarity = 0.6  # Base similarity for text match
                relevance = calculate_relevance_score(
                    similarity=similarity,
                    decay_factor=decay,
                    importance=mem.importance_score,
                )
                results.append(
                    MemorySearchResult(
                        memory=mem,
                        similarity_score=similarity,
                        decay_factor=decay,
                        relevance_score=relevance,
                    )
                )

        # Search working memory
        for mem in self.working.get_active():
            if query_lower in mem.content.lower():
                decay = 1.0  # Working memory is always "fresh"
                similarity = 0.7  # Higher base for task context
                relevance = calculate_relevance_score(
                    similarity=similarity,
                    decay_factor=decay,
                    importance=mem.importance_score,
                )
                results.append(
                    MemorySearchResult(
                        memory=mem,
                        similarity_score=similarity,
                        decay_factor=decay,
                        relevance_score=relevance,
                    )
                )

        # Search long-term memory
        long_term_results = await self.search_long_term(query, limit)
        results.extend(long_term_results)

        # Sort by relevance and limit
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:limit]

    def apply_feedback(
        self,
        memory_id: str,
        signal: FeedbackSignal,
    ) -> float | None:
        """Apply user feedback to update importance score.

        Args:
            memory_id: The memory to update.
            signal: The feedback signal.

        Returns:
            New importance score, or None if memory not found.
        """
        # Check importance cache
        metrics = self._importance_cache.get(memory_id)
        if metrics:
            self.importance_scorer.apply_feedback(metrics, signal)
            new_score = metrics.total_score

            # Update memory if in short-term
            mem = self.short_term.get(memory_id)
            if mem:
                mem.importance_score = new_score
                return new_score

        return None

    async def promote_to_long_term(
        self,
        memory_id: str,
    ) -> LongTermMemory | None:
        """Promote a short-term or working memory to long-term storage.

        Args:
            memory_id: The memory to promote.

        Returns:
            The created LongTermMemory, or None if failed.
        """
        # Find memory in short-term or working
        memory: Memory | None = self.short_term.get(memory_id)
        if not memory:
            memory = self.working.get(memory_id)

        if not memory:
            logger.warning("tiered_memory.promote_not_found", memory_id=memory_id)
            return None

        return await self.add_to_long_term(
            content=memory.content,
            category=memory.category,
            metadata=memory.metadata,
        )

    def get_memory_context(self, query: str, max_length: int = 2000) -> str:
        """Get formatted memory context for prompt injection.

        Args:
            query: The context query.
            max_length: Maximum context string length.

        Returns:
            Formatted context string.
        """
        context_parts = []

        # Add recent short-term messages
        recent = self.short_term.get_recent(5)
        if recent:
            short_term_texts = [f"- {m.content[:200]}" for m in recent]
            context_parts.append("## Recent Context:\n" + "\n".join(short_term_texts))

        # Add active task contexts
        active = self.working.get_active()
        if active:
            working_texts = [f"- [Task {m.task_id}] {m.content[:150]}" for m in active[:3]]
            context_parts.append("## Active Tasks:\n" + "\n".join(working_texts))

        context = "\n\n".join(context_parts)

        # Truncate if needed
        if len(context) > max_length:
            context = context[: max_length - 3] + "..."

        return context

    def clear_session(self) -> None:
        """Clear short-term memory for session end."""
        self.short_term.clear()
        logger.info("tiered_memory.session_cleared", user_id=self.user_id)

    def get_stats(self) -> dict[str, Any]:
        """Get memory system statistics."""
        return {
            "short_term_count": len(self.short_term),
            "short_term_capacity": self.config.short_term_capacity,
            "working_count": len(self.working),
            "working_capacity": self.config.working_memory_capacity,
            "long_term_enabled": self.is_mem0_enabled,
            "user_id": self.user_id,
        }
