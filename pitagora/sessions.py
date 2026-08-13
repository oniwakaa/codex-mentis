"""Session persistence — save/load conversations across restarts."""
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from pitagora.core.constants import SESSIONS_DIR


def save_session(messages: List[Dict], topic: str = "general", mode: str = "study") -> str:
    """Save current conversation to disk. Returns session ID.

    ID includes microseconds so two saves in the same second don't collide
    (the old second-resolution timestamp silently overwrote the prior file).
    """
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    session_id = now.strftime("%Y%m%d_%H%M%S_%f")
    session_data = {
        "id": session_id,
        "topic": topic,
        "mode": mode,
        "created_at": now.isoformat(),
        "message_count": len(messages),
        "messages": messages,
    }

    path = SESSIONS_DIR / f"{session_id}.json"
    with open(path, "w") as f:
        json.dump(session_data, f, indent=2)

    return session_id


def load_session(session_id: str) -> Optional[List[Dict]]:
    """Load a saved session by ID."""
    if not re.fullmatch(r"[\w.-]+", session_id):
        raise ValueError(f"Invalid session id: {session_id}")
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    return data.get("messages", [])


def list_sessions(limit: int = 10) -> List[Dict]:
    """List recent saved sessions."""
    if not SESSIONS_DIR.exists():
        return []
    
    sessions = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            with open(f) as fh:
                data = json.load(fh)
            sessions.append({
                "id": data.get("id", f.stem),
                "topic": data.get("topic", "?"),
                "mode": data.get("mode", "?"),
                "created_at": data.get("created_at", "?"),
                "message_count": data.get("message_count", 0),
            })
        except Exception:
            continue
    return sessions


def delete_session(session_id: str) -> bool:
    """Delete a saved session."""
    if not re.fullmatch(r"[\w.-]+", session_id):
        raise ValueError(f"Invalid session id: {session_id}")
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False
