"""Type definitions for the tiered memory system.

This module defines the core data models for the three-tier memory architecture:
- Short-term Memory: Current session messages (cleared on session end)
- Working Memory: Current task context (24h TTL)
- Long-term Memory: Permanent storage via Mem0
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MemoryTier(str, Enum):
    """Memory tier enumeration."""

    SHORT_TERM = "short_term"
    WORKING = "working"
    LONG_TERM = "long_term"


class MemoryCategory(str, Enum):
    """Memory category enumeration for content classification."""

    # High importance categories
    DECISION = "decision"  # Architecture decisions, design choices
    PREFERENCE = "preference"  # User preferences

    # Medium importance categories
    CODE = "code"  # Code snippets, implementations
    TASK = "task"  # Task contexts, work in progress

    # Lower importance categories
    CONVERSATION = "conversation"  # General chat messages
    DEBUG = "debug"  # Debug information, error logs


# Default importance scores by category
CATEGORY_IMPORTANCE_SCORES: dict[MemoryCategory, float] = {
    MemoryCategory.DECISION: 0.8,
    MemoryCategory.PREFERENCE: 0.8,
    MemoryCategory.CODE: 0.5,
    MemoryCategory.TASK: 0.5,
    MemoryCategory.CONVERSATION: 0.3,
    MemoryCategory.DEBUG: 0.2,
}


@dataclass
class Memory:
    """Base memory data model.

    Attributes:
        id: Unique identifier for the memory.
        content: The memory content text.
        tier: Which tier this memory belongs to.
        category: The category of content.
        created_at: When the memory was created.
        last_accessed: Last time this memory was accessed.
        access_count: Number of times this memory was accessed.
        importance_score: Importance score from 0.0 to 1.0.
        metadata: Additional metadata dictionary.
    """

    id: str
    content: str
    tier: MemoryTier
    category: MemoryCategory = MemoryCategory.CONVERSATION
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    importance_score: float = 0.3
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert memory to dictionary representation."""
        return {
            "id": self.id,
            "content": self.content,
            "tier": self.tier.value,
            "category": self.category.value,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "importance_score": self.importance_score,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Memory":
        """Create memory from dictionary representation."""
        return cls(
            id=data["id"],
            content=data["content"],
            tier=MemoryTier(data["tier"]),
            category=MemoryCategory(data.get("category", "conversation")),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data.get("access_count", 0),
            importance_score=data.get("importance_score", 0.3),
            metadata=data.get("metadata", {}),
        )

    def update_access(self) -> None:
        """Update access time and count."""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class ShortTermMemory(Memory):
    """Short-term memory for current session messages.

    Attributes:
        session_id: The session this memory belongs to.
        message_index: Order index within the session.
    """

    session_id: str = ""
    message_index: int = 0

    def __post_init__(self) -> None:
        """Initialize with SHORT_TERM tier."""
        self.tier = MemoryTier.SHORT_TERM


@dataclass
class WorkingMemory(Memory):
    """Working memory for current task context.

    Attributes:
        task_id: The task this memory is associated with.
        expires_at: When this memory should expire.
    """

    task_id: str = ""
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        """Initialize with WORKING tier and default expiration."""
        self.tier = MemoryTier.WORKING
        if self.expires_at is None:
            from datetime import timedelta

            self.expires_at = datetime.now() + timedelta(hours=24)

    def is_expired(self, current_time: datetime | None = None) -> bool:
        """Check if this working memory has expired."""
        if self.expires_at is None:
            return False
        now = current_time or datetime.now()
        return now > self.expires_at


@dataclass
class LongTermMemory(Memory):
    """Long-term memory stored in Mem0.

    Attributes:
        mem0_id: The ID in Mem0 storage.
        vector_id: The vector store ID for similarity search.
        decay_factor: Current time decay factor.
    """

    mem0_id: str = ""
    vector_id: str = ""
    decay_factor: float = 1.0

    def __post_init__(self) -> None:
        """Initialize with LONG_TERM tier."""
        self.tier = MemoryTier.LONG_TERM


@dataclass
class MemorySearchResult:
    """Result from memory search operation.

    Attributes:
        memory: The memory that matched.
        similarity_score: Similarity score from vector search.
        decay_factor: Time decay factor.
        relevance_score: Combined relevance score.
    """

    memory: Memory
    similarity_score: float = 0.0
    decay_factor: float = 1.0
    relevance_score: float = 0.0

    def calculate_relevance(
        self,
        weights: dict[str, float] | None = None,
    ) -> float:
        """Calculate combined relevance score.

        Args:
            weights: Custom weights for similarity, decay, importance.
                     Defaults to {"similarity": 0.5, "decay": 0.2, "importance": 0.3}

        Returns:
            Combined relevance score.
        """
        if weights is None:
            weights = {"similarity": 0.5, "decay": 0.2, "importance": 0.3}

        self.relevance_score = (
            weights["similarity"] * self.similarity_score
            + weights["decay"] * self.decay_factor
            + weights["importance"] * self.memory.importance_score
        )
        return self.relevance_score


@dataclass
class TieredMemoryConfig:
    """Configuration for tiered memory system.

    Attributes:
        short_term_capacity: Max messages in short-term memory.
        working_memory_capacity: Max task contexts in working memory.
        working_memory_ttl_hours: Hours before working memory expires.
        long_term_search_limit: Max results from long-term search.
        decay_half_life_days: Half-life for time decay calculation.
        min_decay_factor: Minimum decay factor to retain.
    """

    short_term_capacity: int = 100
    working_memory_capacity: int = 10
    working_memory_ttl_hours: int = 24
    long_term_search_limit: int = 5
    decay_half_life_days: float = 30.0
    min_decay_factor: float = 0.1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TieredMemoryConfig":
        """Create config from dictionary."""
        return cls(
            short_term_capacity=data.get("short_term_capacity", 100),
            working_memory_capacity=data.get("working_memory_capacity", 10),
            working_memory_ttl_hours=data.get("working_memory_ttl_hours", 24),
            long_term_search_limit=data.get("long_term_search_limit", 5),
            decay_half_life_days=data.get("decay_half_life_days", 30.0),
            min_decay_factor=data.get("min_decay_factor", 0.1),
        )
