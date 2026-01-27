import datetime
import json
import os
from pathlib import Path

from langchain_core.messages import (
    BaseMessage,
    message_to_dict,
    messages_from_dict,
)


class HistoryManager:
    def __init__(self, history_dir: str | Path | None = None):
        if history_dir is None:
            # Default to ~/.mini-opencode/history
            self.history_dir = Path.home() / ".mini-opencode" / "history"
        else:
            self.history_dir = Path(history_dir)

        try:
            self.history_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Fallback to local directory if home is not writable
            self.history_dir = Path(".history")
            self.history_dir.mkdir(parents=True, exist_ok=True)

    def save_session(
        self, messages: list[BaseMessage], session_id: str | None = None
    ) -> str:
        if not session_id:
            session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        filepath = self.history_dir / f"{session_id}.json"
        data = [message_to_dict(m) for m in messages]

        # Add metadata if needed
        full_data = {
            "session_id": session_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "messages": data,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2)
        return str(filepath)

    def list_sessions(self) -> list[dict]:
        sessions = []
        if not self.history_dir.exists():
            return []

        for p in self.history_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append(
                        {
                            "id": p.stem,
                            "path": str(p),
                            "timestamp": data.get("timestamp", ""),
                            "mtime": os.path.getmtime(p),
                            "preview": self._get_preview(data.get("messages", [])),
                        }
                    )
            except Exception:
                continue

        return sorted(sessions, key=lambda x: x["mtime"], reverse=True)

    def load_session(self, session_id: str) -> list[BaseMessage]:
        filepath = self.history_dir / f"{session_id}.json"
        if not filepath.exists():
            # Try as full path
            filepath = Path(session_id)
            if not filepath.exists():
                raise FileNotFoundError(f"Session {session_id} not found")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages_data = data.get("messages", [])
        return messages_from_dict(messages_data)

    def _get_preview(self, messages: list[dict]) -> str:
        for msg in messages:
            if msg.get("type") == "human":
                content = msg.get("data", {}).get("content", "")
                if isinstance(content, list):
                    # Handle multimodal content if any
                    content = str(content)
                return (content[:50] + "...") if len(content) > 50 else content
        return "No human message"
