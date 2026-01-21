from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea


class ChatInput(TextArea):
    """Custom input for chat with multi-line support"""

    BINDINGS = [
        Binding("enter", "submit", "Send message", show=False),
        Binding("shift+enter", "newline", "New line", show=False),
    ]

    class Submitted(Message):
        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()

    DEFAULT_CSS = """
    ChatInput {
        dock: bottom;
        margin: 1 2;
        padding: 0 1;
        background: $boost;
        border: none;
        width: 100%;
        height: 5;
        overflow-y: auto;
    }

    ChatInput:focus {
        border: none;
        background: $boost;
    }
    """

    def __init__(self, *args, **kwargs):
        # Pop placeholder as TextArea doesn't support it in some versions
        kwargs.pop("placeholder", None)
        super().__init__(*args, **kwargs)
        self.show_line_numbers = False
        self.soft_wrap = True

    def action_submit(self) -> None:
        if self.text.strip():
            self.post_message(self.Submitted(self.text))
            self.text = ""

    def action_newline(self) -> None:
        self.insert("\n")
