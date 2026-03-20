from textual import events
from textual.containers import VerticalScroll
from textual.widgets import Static


class TerminalView(VerticalScroll):
    """Terminal view component with mouse selection support"""

    DEFAULT_CSS = """
    TerminalView {
        padding: 1 2;
        scrollbar-size: 1 1;
        scrollbar-background: $surface;
        scrollbar-color: $primary-darken-2;
        scrollbar-color-hover: $primary;
        scrollbar-color-active: $primary-lighten-1;
    }

    TerminalView Static {
        width: 1fr;
    }

    TerminalView Static.muted {
        color: $text-muted;
    }

    TerminalView Static.selected {
        background: $primary;
        color: $foreground;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selecting = False
        self._selection_start = None
        self._selection_end = None
        self._selected_items = []

    def write(self, text: str, muted: bool = False) -> None:
        """Add output to terminal"""
        if self._selecting:
            self._selecting = False
            self._clear_selection()
        item = Static(text, classes=f"{'muted' if muted else ''}")
        self.mount(item)
        self.scroll_end(animate=True)

    def clear(self) -> None:
        """Clear all output from terminal"""
        self._selected_items.clear()
        self._selection_start = None
        self._selection_end = None
        for child in list(self.children):
            child.remove()

    def _clear_selection(self) -> None:
        """Clear current selection"""
        for item in self._selected_items:
            item.remove_class("selected")
        self._selected_items.clear()
        self._selection_start = None
        self._selection_end = None

    def _update_selection(self) -> None:
        """Update selection highlighting"""
        self._clear_selection()
        
        if self._selection_start is None or self._selection_end is None:
            return
        
        children = list(self.children)
        if not children:
            return
        
        start_idx = min(self._selection_start, self._selection_end)
        end_idx = max(self._selection_start, self._selection_end)
        
        start_idx = max(0, min(start_idx, len(children) - 1))
        end_idx = max(0, min(end_idx, len(children) - 1))
        
        for i in range(start_idx, end_idx + 1):
            if i < len(children):
                child = children[i]
                if isinstance(child, Static):
                    child.add_class("selected")
                    self._selected_items.append(child)

    def _get_item_index_at_y(self, y: float) -> int:
        """Get the item index at a given y coordinate, accounting for scrolling"""
        scroll_offset = self.scroll_target_y
        absolute_y = y + scroll_offset
        children = list(self.children)
        if not children:
            return 0
        
        item_height = 1
        index = int(absolute_y / item_height)
        return max(0, min(index, len(children) - 1))

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Handle mouse button press - start selection"""
        self._selecting = True
        children = list(self.children)
        if children:
            item_index = self._get_item_index_at_y(event.y)
            self._selection_start = item_index
            self._selection_end = item_index
            self._update_selection()
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Handle mouse button release - end selection"""
        self._selecting = False
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Handle mouse movement - update selection"""
        if self._selecting:
            children = list(self.children)
            if children:
                item_index = self._get_item_index_at_y(event.y)
                self._selection_end = item_index
                self._update_selection()
                
                auto_scroll_margin = 3
                if event.y < auto_scroll_margin:
                    self.scroll_target_y = max(0, self.scroll_target_y - 2)
                elif event.y > self.size.height - auto_scroll_margin:
                    self.scroll_target_y = min(
                        self.max_scroll_y,
                        self.scroll_target_y + 2
                    )
            event.stop()

    def on_click(self, event: events.Click) -> None:
        """Handle click - clear selection if not dragging"""
        if not self._selecting:
            self._clear_selection()
        event.stop()
