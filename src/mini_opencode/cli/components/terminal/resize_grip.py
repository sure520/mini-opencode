from textual import events
from textual.app import ComposeResult
from textual.widgets import Static
from textual.widget import Widget


class ResizeGrip(Widget):
    """A draggable grip for resizing terminal area"""

    DEFAULT_CSS = """
    ResizeGrip {
        height: 0;
        width: 1fr;
        padding: 1 0;
        background: $panel;
    }

    ResizeGrip:hover {
        background: $primary;
    }

    ResizeGrip.dragging {
        background: $primary-darken-1;
    }

    ResizeGrip Static {
        height: 0;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dragging = False
        self._start_y = 0
        self._start_height = 0

    def compose(self) -> ComposeResult:
        """Compose the grip with an empty static widget"""
        yield Static("")

    def on_enter(self, event: events.Enter) -> None:
        """Show grip on mouse enter"""
        self.styles.height = "1"

    def on_leave(self, event: events.Leave) -> None:
        """Hide grip on mouse leave if not dragging"""
        if not self._dragging:
            self.styles.height = "0"

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Start dragging"""
        self._dragging = True
        self.add_class("dragging")
        self._start_y = event.screen_y
        try:
            tabs = self.app.query_one("#bottom-right-tabs")
            self._start_height = tabs.size.height
        except Exception:
            pass
        self.capture_mouse()
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Stop dragging"""
        self._dragging = False
        self.remove_class("dragging")
        self.release_mouse()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Handle dragging"""
        if self._dragging:
            delta_y = self._start_y - event.screen_y
            try:
                tabs = self.app.query_one("#bottom-right-tabs")
                new_height = self._start_height + delta_y
                
                min_height = 5
                max_height = self.app.size.height - 1
                
                if new_height < min_height:
                    new_height = min_height
                elif new_height > max_height:
                    new_height = max_height
                
                tabs.styles.height = f"{new_height}"
            except Exception:
                pass
            event.stop()

    def on_click(self, event: events.Click) -> None:
        """Prevent click from propagating"""
        event.stop()
