"""Time decay algorithms for the tiered memory system.

This module implements time-based decay functions for memory relevance scoring.
The primary algorithm uses exponential decay with configurable half-life.
"""

import math
from datetime import datetime


def calculate_time_decay(
    created_at: datetime,
    current_time: datetime | None = None,
    half_life_days: float = 30.0,
    min_decay: float = 0.1,
) -> float:
    """Calculate time decay factor using exponential decay model.

    The decay follows the formula:
        decay_factor = 0.5 ^ (elapsed_days / half_life_days)

    This means:
    - At t=0 (just created): decay_factor = 1.0
    - At t=half_life: decay_factor = 0.5
    - At t=2*half_life: decay_factor = 0.25

    Args:
        created_at: When the memory was created.
        current_time: Current time for calculation. Defaults to now.
        half_life_days: Number of days for half-life decay. Default 30 days.
        min_decay: Minimum decay factor to prevent complete forgetting.
                   Default 0.1 (10% retention minimum).

    Returns:
        Decay factor in range [min_decay, 1.0].

    Examples:
        >>> from datetime import datetime, timedelta
        >>> now = datetime.now()
        >>> # Just created - full relevance
        >>> calculate_time_decay(now, now)
        1.0
        >>> # 30 days old - half relevance
        >>> old = now - timedelta(days=30)
        >>> round(calculate_time_decay(old, now), 2)
        0.5
        >>> # 60 days old - quarter relevance
        >>> older = now - timedelta(days=60)
        >>> round(calculate_time_decay(older, now), 2)
        0.25
    """
    if current_time is None:
        current_time = datetime.now()

    # Handle future dates (shouldn't happen, but be safe)
    if created_at > current_time:
        return 1.0

    # Calculate elapsed days
    elapsed_seconds = (current_time - created_at).total_seconds()
    elapsed_days = elapsed_seconds / 86400  # 24 * 60 * 60

    # Handle zero half-life (no decay)
    if half_life_days <= 0:
        return 1.0

    # Exponential decay: decay_factor = 0.5 ^ (elapsed_days / half_life_days)
    decay_factor = math.pow(0.5, elapsed_days / half_life_days)

    # Ensure minimum decay factor
    return max(min_decay, decay_factor)


def calculate_access_boost(
    access_count: int,
    last_accessed: datetime,
    current_time: datetime | None = None,
    boost_factor: float = 0.1,
    recent_window_hours: float = 24.0,
) -> float:
    """Calculate boost factor based on access patterns.

    Recently and frequently accessed memories get a relevance boost.

    Args:
        access_count: Number of times the memory was accessed.
        last_accessed: When the memory was last accessed.
        current_time: Current time for calculation. Defaults to now.
        boost_factor: Base boost per access. Default 0.1.
        recent_window_hours: Hours considered "recent" for boost. Default 24h.

    Returns:
        Boost factor in range [0.0, 0.5] to add to base relevance.

    Examples:
        >>> from datetime import datetime, timedelta
        >>> now = datetime.now()
        >>> # Never accessed - no boost
        >>> calculate_access_boost(0, now, now)
        0.0
        >>> # Accessed recently - small boost
        >>> calculate_access_boost(1, now, now)
        0.1
    """
    if current_time is None:
        current_time = datetime.now()

    if access_count == 0:
        return 0.0

    # Base boost from access count (diminishing returns)
    # Using log to prevent unbounded growth
    count_boost = boost_factor * math.log(access_count + 1)

    # Recency boost - higher if accessed recently
    elapsed_hours = (current_time - last_accessed).total_seconds() / 3600

    if elapsed_hours <= recent_window_hours:
        # Recent access gets full count boost
        recency_multiplier = 1.0
    else:
        # Older access gets diminishing boost
        hours_past_window = elapsed_hours - recent_window_hours
        recency_multiplier = math.exp(-hours_past_window / 168)  # 1 week half-life

    total_boost = count_boost * recency_multiplier

    # Cap at 0.5 to prevent overwhelming the base score
    return min(0.5, total_boost)


def calculate_relevance_score(
    similarity: float,
    decay_factor: float,
    importance: float,
    access_boost: float = 0.0,
    weights: dict[str, float] | None = None,
) -> float:
    """Calculate combined relevance score for memory retrieval.

    The score combines multiple factors:
    - Similarity: How well the memory matches the query (0-1)
    - Decay: Time-based relevance decay (0-1)
    - Importance: Content importance score (0-1)
    - Access boost: Bonus for frequently accessed memories (0-0.5)

    Formula:
        score = w1*similarity + w2*decay + w3*importance + access_boost

    Args:
        similarity: Semantic similarity score from vector search.
        decay_factor: Time decay factor from calculate_time_decay.
        importance: Content importance score.
        access_boost: Boost from access patterns.
        weights: Custom weights dict with keys 'similarity', 'decay', 'importance'.
                 Defaults to {"similarity": 0.5, "decay": 0.2, "importance": 0.3}.

    Returns:
        Combined relevance score in range [0.0, 1.5].

    Examples:
        >>> # High similarity, recent, important memory
        >>> calculate_relevance_score(0.9, 1.0, 0.8, 0.2)
        1.09
        >>> # Low similarity, old, unimportant memory
        >>> calculate_relevance_score(0.3, 0.2, 0.2, 0.0)
        0.25
    """
    if weights is None:
        weights = {"similarity": 0.5, "decay": 0.2, "importance": 0.3}

    base_score = (
        weights["similarity"] * similarity
        + weights["decay"] * decay_factor
        + weights["importance"] * importance
    )

    return base_score + access_boost


def get_decay_tier(decay_factor: float) -> str:
    """Get a human-readable decay tier description.

    Args:
        decay_factor: The decay factor (0-1).

    Returns:
        Tier description string.
    """
    if decay_factor >= 0.8:
        return "fresh"  # < 1 week old
    elif decay_factor >= 0.5:
        return "recent"  # < 1 month old
    elif decay_factor >= 0.25:
        return "aging"  # < 2 months old
    else:
        return "old"  # > 2 months old


class DecayCalculator:
    """Calculator for time-based memory decay.

    This class provides a configured instance for calculating decay factors
    with consistent parameters.
    """

    def __init__(
        self,
        half_life_days: float = 30.0,
        min_decay: float = 0.1,
        boost_factor: float = 0.1,
        recent_window_hours: float = 24.0,
    ) -> None:
        """Initialize the decay calculator.

        Args:
            half_life_days: Number of days for half-life decay.
            min_decay: Minimum decay factor.
            boost_factor: Base boost per access.
            recent_window_hours: Hours considered "recent".
        """
        self.half_life_days = half_life_days
        self.min_decay = min_decay
        self.boost_factor = boost_factor
        self.recent_window_hours = recent_window_hours

    def calculate_decay(
        self,
        created_at: datetime,
        current_time: datetime | None = None,
    ) -> float:
        """Calculate time decay factor.

        Args:
            created_at: When the memory was created.
            current_time: Current time for calculation.

        Returns:
            Decay factor in range [min_decay, 1.0].
        """
        return calculate_time_decay(
            created_at=created_at,
            current_time=current_time,
            half_life_days=self.half_life_days,
            min_decay=self.min_decay,
        )

    def calculate_boost(
        self,
        access_count: int,
        last_accessed: datetime,
        current_time: datetime | None = None,
    ) -> float:
        """Calculate access boost factor.

        Args:
            access_count: Number of times accessed.
            last_accessed: When last accessed.
            current_time: Current time for calculation.

        Returns:
            Boost factor in range [0.0, 0.5].
        """
        return calculate_access_boost(
            access_count=access_count,
            last_accessed=last_accessed,
            current_time=current_time,
            boost_factor=self.boost_factor,
            recent_window_hours=self.recent_window_hours,
        )

    def calculate_full_relevance(
        self,
        similarity: float,
        created_at: datetime,
        importance: float,
        access_count: int = 0,
        last_accessed: datetime | None = None,
        current_time: datetime | None = None,
        weights: dict[str, float] | None = None,
    ) -> float:
        """Calculate full relevance score with all factors.

        Args:
            similarity: Semantic similarity score.
            created_at: When the memory was created.
            importance: Content importance score.
            access_count: Number of times accessed.
            last_accessed: When last accessed.
            current_time: Current time for calculation.
            weights: Custom weights for score components.

        Returns:
            Combined relevance score.
        """
        if current_time is None:
            current_time = datetime.now()

        if last_accessed is None:
            last_accessed = created_at

        decay = self.calculate_decay(created_at, current_time)
        boost = self.calculate_boost(access_count, last_accessed, current_time)

        return calculate_relevance_score(
            similarity=similarity,
            decay_factor=decay,
            importance=importance,
            access_boost=boost,
            weights=weights,
        )
