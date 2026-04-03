"""Tiered memory system for hierarchical memory management.

This module provides a three-tier memory architecture:
- Short-term Memory: Current session messages (cleared on session end)
- Working Memory: Current task context (24h TTL)
- Long-term Memory: Permanent storage via Mem0 with time decay and importance scoring

Example usage:
    from mini_opencode.services.memory import TieredMemoryManager, MemoryCategory

    # Initialize manager
    manager = TieredMemoryManager(user_id="user123")

    # Add to short-term memory
    manager.add_message("User asked about Python decorators")

    # Add task context
    manager.add_task_context(
        task_id="task1",
        content="Working on implementing caching decorator"
    )

    # Search with relevance scoring
    results = await manager.search_all_tiers("decorators")

    # Apply user feedback
    manager.apply_feedback(memory_id, FeedbackSignal.THUMBS_UP)
"""

from .decay import (
    DecayCalculator,
    calculate_access_boost,
    calculate_relevance_score,
    calculate_time_decay,
    get_decay_tier,
)
from .importance import (
    DEFAULT_FEEDBACK_WEIGHTS,
    ContentAnalyzer,
    FeedbackEvent,
    FeedbackSignal,
    ImportanceMetrics,
    ImportanceScorer,
)
from .tiered_memory import (
    ShortTermStore,
    TieredMemoryManager,
    WorkingStore,
)
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

__all__ = [
    # Types
    "Memory",
    "MemoryTier",
    "MemoryCategory",
    "ShortTermMemory",
    "WorkingMemory",
    "LongTermMemory",
    "MemorySearchResult",
    "TieredMemoryConfig",
    "CATEGORY_IMPORTANCE_SCORES",
    # Decay
    "calculate_time_decay",
    "calculate_access_boost",
    "calculate_relevance_score",
    "get_decay_tier",
    "DecayCalculator",
    # Importance
    "FeedbackSignal",
    "FeedbackEvent",
    "ImportanceMetrics",
    "ImportanceScorer",
    "ContentAnalyzer",
    "DEFAULT_FEEDBACK_WEIGHTS",
    # Manager
    "TieredMemoryManager",
    "ShortTermStore",
    "WorkingStore",
]
