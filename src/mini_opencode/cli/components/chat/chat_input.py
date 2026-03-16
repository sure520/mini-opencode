from textual import events, on
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widgets import Button, TextArea


class ChatTextArea(TextArea):
    """Custom TextArea that captures Enter and Shift+Enter keys."""

    class EnterPressed(Message):
        """Message sent when Enter is pressed (without Shift)."""
        pass

    class ShiftEnterPressed(Message):
        """Message sent when Shift+Enter is pressed."""
        pass

    def on_key(self, event: events.Key) -> None:
        if event.key == "shift+enter":
            self.post_message(self.ShiftEnterPressed())
            event.prevent_default()
            event.stop()
        elif event.key == "enter":
            self.post_message(self.EnterPressed())
            event.prevent_default()
            event.stop()


class ChatInput(Container):
    """Custom input for chat with multi-line support and send/stop button"""

    class Submitted(Message):
        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()

    class StopRequested(Message):
        def __init__(self) -> None:
            super().__init__()

    class NavigateSuggestion(Message):
        def __init__(self, direction: int) -> None:
            self.direction = direction
            super().__init__()

    class SelectSuggestion(Message):
        def __init__(self) -> None:
            super().__init__()

    DEFAULT_CSS = """
    ChatInput {
        dock: bottom;
        margin: 1 2;
        padding: 0;
        background: $boost;
        border: none;
        width: 100%;
        height: auto;
    }

    ChatInput > #input-container {
        height: 3;
        background: $boost;
        border: none;
    }

    ChatInput ChatTextArea {
        width: 100%;
        height: 100%;
        background: $boost;
        border: none;
        padding: 0 1;
    }

    ChatInput ChatTextArea:focus {
        border: none;
        background: $boost;
    }

    ChatInput #send-button {
        width: 10;
        dock: right;
        background: $primary;
        color: $text;
        border: none;
        margin-left: 1;
    }

    ChatInput #send-button:hover {
        background: $accent;
    }

    ChatInput #send-button:disabled {
        background: $surface;
        color: $text-muted;
    }

    ChatInput #send-button.stop-mode {
        background: $error;
        color: $text;
    }

    ChatInput #send-button.stop-mode:hover {
        background: darkred;
    }
    """

    def __init__(self, *args, **kwargs):
        placeholder = kwargs.pop(
            "placeholder",
            "输入消息，Enter 发送，Shift+Enter 换行",
        )
        super().__init__(*args, **kwargs)
        self._placeholder = placeholder
        self._text_area: ChatTextArea | None = None
        self._send_button: Button | None = None
        self.suggestions_active = False
        self._is_generating = False

    def compose(self) -> None:
        with Horizontal(id="input-container"):
            yield ChatTextArea(
                id="chat-textarea",
                placeholder=self._placeholder,
                show_line_numbers=False,
                soft_wrap=True,
            )
            yield Button("发送", id="send-button", variant="primary")

    def on_mount(self) -> None:
        self._text_area = self.query_one("#chat-textarea", ChatTextArea)
        self._send_button = self.query_one("#send-button", Button)
        self._update_button_state()

    @property
    def text(self) -> str:
        if self._text_area:
            return self._text_area.text
        return ""

    @text.setter
    def text(self, value: str) -> None:
        if self._text_area:
            self._text_area.text = value
            self._update_button_state()

    @property
    def is_generating(self) -> bool:
        return self._is_generating

    @is_generating.setter
    def is_generating(self, value: bool) -> None:
        self._is_generating = value
        self._update_button_state()

    def _update_button_state(self) -> None:
        if not self._send_button:
            return

        if self._is_generating:
            self._send_button.label = "终止"
            self._send_button.variant = "error"
            self._send_button.disabled = False
            self._send_button.remove_class("stop-mode")
            self._send_button.add_class("stop-mode")
        elif self.text.strip():
            self._send_button.label = "发送"
            self._send_button.variant = "primary"
            self._send_button.disabled = False
            self._send_button.remove_class("stop-mode")
        else:
            self._send_button.label = "发送"
            self._send_button.variant = "primary"
            self._send_button.disabled = True
            self._send_button.remove_class("stop-mode")

    def focus(self) -> None:
        if self._text_area:
            self._text_area.focus()

    @on(ChatTextArea.Changed)
    def on_text_changed(self, event: ChatTextArea.Changed) -> None:
        self._update_button_state()

    @on(ChatTextArea.EnterPressed)
    def on_enter_pressed(self, event: ChatTextArea.EnterPressed) -> None:
        if self.suggestions_active:
            self.post_message(self.SelectSuggestion())
        else:
            self.action_submit()

    @on(ChatTextArea.ShiftEnterPressed)
    def on_shift_enter_pressed(self, event: ChatTextArea.ShiftEnterPressed) -> None:
        self.action_newline()

    def action_submit(self) -> None:
        if self.text.strip() and not self._is_generating:
            self.post_message(self.Submitted(self.text))
            self.text = ""

    def action_newline(self) -> None:
        if self._text_area:
            self._text_area.insert("\n")

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-button":
            if self._is_generating:
                self.post_message(self.StopRequested())
            else:
                self.action_submit()
