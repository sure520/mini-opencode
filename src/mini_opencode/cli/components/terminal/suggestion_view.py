from typing import Any, Dict, List, Optional, Union

from textual.containers import Vertical
from textual.widgets import Static


class SuggestionView(Vertical):
    """Component to display slash command suggestions"""

    DEFAULT_CSS = """
    SuggestionView {
        background: $boost;
        border: solid $primary;
        height: auto;
        max-height: 10;
        display: none;
        padding: 0 1;
    }

    SuggestionView.visible {
        display: block;
    }

    SuggestionView Static {
        width: 100%;
        padding: 0 1;
    }

    SuggestionView Static.selected {
        background: $primary;
        color: $foreground;
        text-style: bold;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.suggestions: List[Dict[str, Any]] = []
        self.selected_index: int = 0

    def set_suggestions(self, suggestions: List[Union[str, Dict[str, Any]]]) -> None:
        """Update the list of suggestions.

        Args:
            suggestions: A list of either strings or dicts with 'text' and 'value'.
        """
        self.suggestions = []
        for s in suggestions:
            if isinstance(s, str):
                self.suggestions.append({"text": s, "value": s})
            else:
                self.suggestions.append(s)

        self.selected_index = 0
        self._refresh_list()

        if self.suggestions:
            self.add_class("visible")
        else:
            self.remove_class("visible")

    def move_selection(self, direction: int) -> None:
        """Move the selection up or down"""
        if not self.suggestions:
            return

        self.selected_index = (self.selected_index + direction) % len(self.suggestions)
        self._refresh_list()

    def get_selected(self) -> Optional[Dict[str, Any]]:
        """Get the currently selected suggestion"""
        if 0 <= self.selected_index < len(self.suggestions):
            return self.suggestions[self.selected_index]
        return None

    def _refresh_list(self) -> None:
        """Refresh the displayed list of suggestions"""
        self.query(Static).remove()
        for i, suggestion in enumerate(self.suggestions):
            is_selected = i == self.selected_index
            self.mount(
                Static(
                    suggestion["text"],
                    classes="selected" if is_selected else "",
                )
            )
