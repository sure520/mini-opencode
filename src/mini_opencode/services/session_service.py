"""Session service for managing session state."""

from typing import Dict, Any, Optional
from datetime import datetime


class SessionService:
    """Service for managing session state and persistence."""

    def __init__(self):
        """Initialize the session service."""
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, session_id: str) -> Dict[str, Any]:
        """Create a new session.

        Args:
            session_id: The unique session ID.

        Returns:
            Dict[str, Any]: The created session.
        """
        session = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "state": {},
            "messages": []
        }
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID.

        Args:
            session_id: The session ID.

        Returns:
            Optional[Dict[str, Any]]: The session if found, None otherwise.
        """
        session = self._sessions.get(session_id)
        if session:
            # Update last activity
            session["last_activity"] = datetime.now().isoformat()
        return session

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update a session.

        Args:
            session_id: The session ID.
            updates: Updates to apply to the session.

        Returns:
            bool: True if session was updated, False otherwise.
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.update(updates)
        session["last_activity"] = datetime.now().isoformat()
        return True

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: The session ID.

        Returns:
            bool: True if session was deleted, False otherwise.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[Dict[str, Any]]:
        """List all sessions.

        Returns:
            list[Dict[str, Any]]: List of sessions.
        """
        return list(self._sessions.values())

    def cleanup_inactive_sessions(self, max_inactive_minutes: int = 30) -> int:
        """Clean up inactive sessions.

        Args:
            max_inactive_minutes: Maximum inactive minutes before session is cleaned up.

        Returns:
            int: Number of sessions cleaned up.
        """
        now = datetime.now()
        to_delete = []

        for session_id, session in self._sessions.items():
            last_activity = datetime.fromisoformat(session["last_activity"])
            if (now - last_activity).total_seconds() / 60 > max_inactive_minutes:
                to_delete.append(session_id)

        for session_id in to_delete:
            del self._sessions[session_id]

        return len(to_delete)
