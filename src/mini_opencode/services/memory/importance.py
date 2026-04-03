"""Importance scoring for the tiered memory system.

This module implements importance scoring based on:
1. Content type/category
2. User explicit feedback (thumbs up/down, copy, edit)
3. Implicit signals (execution success, test coverage)
4. Reference frequency
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .types import CATEGORY_IMPORTANCE_SCORES, MemoryCategory


class FeedbackSignal(str, Enum):
    """User feedback signals for importance scoring."""

    # Positive signals
    THUMBS_UP = "thumbs_up"  # User explicitly liked
    COPY = "copy"  # User copied the content
    EDIT_PRESERVE = "edit_preserve"  # User edited but kept core content
    EXECUTION_SUCCESS = "execution_success"  # Code executed successfully
    TEST_COVERED = "test_covered"  # Code is covered by tests

    # Negative signals
    THUMBS_DOWN = "thumbs_down"  # User explicitly disliked
    DELETE = "delete"  # User deleted the content
    EXECUTION_FAILED = "execution_failed"  # Code failed to execute

    # Neutral signals
    VIEW = "view"  # User viewed but took no action
    REFERENCE = "reference"  # Content was referenced


# Default feedback weights
DEFAULT_FEEDBACK_WEIGHTS: dict[FeedbackSignal, float] = {
    # Positive signals (add to importance)
    FeedbackSignal.THUMBS_UP: 0.3,
    FeedbackSignal.COPY: 0.1,
    FeedbackSignal.EDIT_PRESERVE: 0.2,
    FeedbackSignal.EXECUTION_SUCCESS: 0.15,
    FeedbackSignal.TEST_COVERED: 0.15,
    # Negative signals (subtract from importance)
    FeedbackSignal.THUMBS_DOWN: -0.3,
    FeedbackSignal.DELETE: -0.4,
    FeedbackSignal.EXECUTION_FAILED: -0.1,
    # Neutral signals (small boost)
    FeedbackSignal.VIEW: 0.02,
    FeedbackSignal.REFERENCE: 0.05,
}


@dataclass
class FeedbackEvent:
    """Record of a user feedback event.

    Attributes:
        signal: The type of feedback signal.
        timestamp: When the feedback was given.
        metadata: Additional context about the feedback.
    """

    signal: FeedbackSignal
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportanceMetrics:
    """Metrics tracking for importance calculation.

    Attributes:
        base_score: Initial score based on content category.
        feedback_score: Accumulated score from user feedback.
        reference_count: Number of times this content was referenced.
        positive_signals: Count of positive feedback signals.
        negative_signals: Count of negative feedback signals.
        last_updated: Last time the score was updated.
    """

    base_score: float = 0.3
    feedback_score: float = 0.0
    reference_count: int = 0
    positive_signals: int = 0
    negative_signals: int = 0
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def total_score(self) -> float:
        """Calculate total importance score."""
        # Reference bonus with diminishing returns
        reference_bonus = 0.1 * math.log(self.reference_count + 1) if self.reference_count > 0 else 0.0

        total = self.base_score + self.feedback_score + reference_bonus

        # Clamp to valid range [0.0, 1.0]
        return max(0.0, min(1.0, total))


class ImportanceScorer:
    """Scorer for calculating and updating memory importance.

    This class manages importance scoring based on content type,
    user feedback, and implicit signals.
    """

    def __init__(
        self,
        feedback_weights: dict[FeedbackSignal, float] | None = None,
        category_scores: dict[MemoryCategory, float] | None = None,
    ) -> None:
        """Initialize the importance scorer.

        Args:
            feedback_weights: Custom weights for feedback signals.
            category_scores: Custom base scores for content categories.
        """
        self.feedback_weights = feedback_weights or DEFAULT_FEEDBACK_WEIGHTS.copy()
        self.category_scores = category_scores or CATEGORY_IMPORTANCE_SCORES.copy()

    def calculate_initial_score(
        self,
        content: str,
        category: MemoryCategory | None = None,
    ) -> float:
        """Calculate initial importance score for new content.

        Args:
            content: The content text.
            category: The content category. If None, will be auto-detected.

        Returns:
            Initial importance score in range [0.0, 1.0].
        """
        if category is None:
            category = self._detect_category(content)

        return self.category_scores.get(category, 0.3)

    def _detect_category(self, content: str) -> MemoryCategory:
        """Auto-detect content category from text.

        Args:
            content: The content text to analyze.

        Returns:
            Detected memory category.
        """
        content_lower = content.lower()

        # Decision indicators
        decision_keywords = [
            "decided",
            "decision",
            "choose",
            "chose",
            "architecture",
            "design",
            "approach",
            "strategy",
            "pattern",
            "framework",
            "selected",
            "prefer",
        ]
        if any(kw in content_lower for kw in decision_keywords):
            return MemoryCategory.DECISION

        # Preference indicators
        preference_keywords = [
            "i like",
            "i prefer",
            "i want",
            "always use",
            "never use",
            "my style",
            "settings",
            "configuration",
        ]
        if any(kw in content_lower for kw in preference_keywords):
            return MemoryCategory.PREFERENCE

        # Code indicators
        code_indicators = [
            "```",
            "def ",
            "class ",
            "function",
            "import ",
            "const ",
            "var ",
            "let ",
            "async ",
            "await ",
        ]
        if any(ind in content for ind in code_indicators):
            return MemoryCategory.CODE

        # Task indicators
        task_keywords = [
            "task",
            "todo",
            "implement",
            "fix",
            "bug",
            "feature",
            "working on",
            "in progress",
        ]
        if any(kw in content_lower for kw in task_keywords):
            return MemoryCategory.TASK

        # Debug indicators
        debug_keywords = [
            "error",
            "exception",
            "traceback",
            "debug",
            "stack trace",
            "failed",
            "crash",
        ]
        if any(kw in content_lower for kw in debug_keywords):
            return MemoryCategory.DEBUG

        # Default to conversation
        return MemoryCategory.CONVERSATION

    def apply_feedback(
        self,
        metrics: ImportanceMetrics,
        signal: FeedbackSignal,
    ) -> ImportanceMetrics:
        """Apply a feedback signal to update importance metrics.

        Args:
            metrics: Current importance metrics.
            signal: The feedback signal to apply.

        Returns:
            Updated importance metrics.
        """
        weight = self.feedback_weights.get(signal, 0.0)

        # Update metrics
        metrics.feedback_score += weight
        metrics.last_updated = datetime.now()

        # Track signal counts
        if weight > 0:
            metrics.positive_signals += 1
        elif weight < 0:
            metrics.negative_signals += 1

        # Track references
        if signal == FeedbackSignal.REFERENCE:
            metrics.reference_count += 1

        return metrics

    def process_feedback_events(
        self,
        metrics: ImportanceMetrics,
        events: list[FeedbackEvent],
    ) -> ImportanceMetrics:
        """Process multiple feedback events.

        Args:
            metrics: Current importance metrics.
            events: List of feedback events to process.

        Returns:
            Updated importance metrics.
        """
        for event in events:
            metrics = self.apply_feedback(metrics, event.signal)

        return metrics

    def create_metrics(
        self,
        content: str,
        category: MemoryCategory | None = None,
    ) -> ImportanceMetrics:
        """Create new importance metrics for content.

        Args:
            content: The content text.
            category: The content category.

        Returns:
            New ImportanceMetrics instance.
        """
        base_score = self.calculate_initial_score(content, category)
        return ImportanceMetrics(base_score=base_score)

    def get_importance_level(self, score: float) -> str:
        """Get human-readable importance level.

        Args:
            score: The importance score.

        Returns:
            Level description string.
        """
        if score >= 0.8:
            return "critical"
        elif score >= 0.6:
            return "high"
        elif score >= 0.4:
            return "medium"
        elif score >= 0.2:
            return "low"
        else:
            return "minimal"


class ContentAnalyzer:
    """Analyzer for extracting importance signals from content.

    This class provides utilities for analyzing content to determine
    importance-related characteristics.
    """

    def __init__(self) -> None:
        """Initialize the content analyzer."""
        self.code_extensions = {
            ".py",
            ".js",
            ".ts",
            ".java",
            ".go",
            ".rs",
            ".cpp",
            ".c",
            ".rb",
            ".php",
        }

    def analyze_content(self, content: str) -> dict[str, Any]:
        """Analyze content for importance indicators.

        Args:
            content: The content to analyze.

        Returns:
            Dictionary with analysis results.
        """
        return {
            "length": len(content),
            "has_code": self._has_code_block(content),
            "has_decision": self._has_decision_language(content),
            "complexity": self._estimate_complexity(content),
            "actionable": self._is_actionable(content),
        }

    def _has_code_block(self, content: str) -> bool:
        """Check if content contains code blocks."""
        return "```" in content or "\t" in content.split("\n")[0] if "\n" in content else False

    def _has_decision_language(self, content: str) -> bool:
        """Check if content contains decision language."""
        decision_phrases = [
            "we decided",
            "i chose",
            "the approach",
            "architecture decision",
            "design choice",
            "selected",
            "going with",
            "opted for",
        ]
        content_lower = content.lower()
        return any(phrase in content_lower for phrase in decision_phrases)

    def _estimate_complexity(self, content: str) -> str:
        """Estimate content complexity."""
        length = len(content)
        if length > 2000:
            return "high"
        elif length > 500:
            return "medium"
        else:
            return "low"

    def _is_actionable(self, content: str) -> bool:
        """Check if content is actionable (contains tasks/actions)."""
        action_phrases = [
            "todo",
            "fix",
            "implement",
            "add",
            "remove",
            "update",
            "change",
            "refactor",
            "should",
            "need to",
            "must",
        ]
        content_lower = content.lower()
        return any(phrase in content_lower for phrase in action_phrases)
