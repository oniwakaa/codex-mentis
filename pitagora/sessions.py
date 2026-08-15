"""Session persistence — save/load conversations across restarts."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pitagora.core.constants import SESSIONS_DIR


@dataclass
class Session:
    id: str
    topic: str = "general"
    mode: str = "study"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    messages: list[dict] = field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    iteration_count: int = 0
    tool_calls: list[dict] = field(default_factory=list)

    @property
    def session_id(self) -> str:
        return self.id

    def append(self, role: str, content: str, **extra: Any) -> None:
        self.messages.append({"role": role, "content": content, **extra})

    def replay(self) -> list[dict]:
        """Return messages for LLM context (after compaction)."""
        from pitagora.agents.context import ContextManager

        cm = ContextManager()
        if cm.needs_compaction(self.messages):
            return cm.compact(self.messages)
        return self.messages

    def record_turn(self, tokens: int, cost_usd: float, tool_call: dict | None = None) -> None:
        self.total_tokens += tokens
        self.total_cost_usd += cost_usd
        self.iteration_count += 1
        if tool_call is not None:
            self.tool_calls.append(tool_call)

    def get_summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "mode": self.mode,
            "created_at": self.created_at,
            "message_count": len(self.messages),
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "iteration_count": self.iteration_count,
            "tool_calls": self.tool_calls,
        }

    def to_dict(self) -> dict[str, Any]:
        d = self.get_summary()
        d["messages"] = self.messages
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        return cls(
            id=data.get("id", ""),
            topic=data.get("topic", "general"),
            mode=data.get("mode", "study"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            messages=data.get("messages", []),
            total_tokens=data.get("total_tokens", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            iteration_count=data.get("iteration_count", 0),
            tool_calls=data.get("tool_calls", []),
        )

    @classmethod
    def load(cls, path: Path) -> "Session":
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)

    def save(self, dir_path: Path | None = None) -> Path:
        target_dir = dir_path or SESSIONS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{self.id}.json"
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path


def save_session(
    messages: list[dict] | Session,
    topic: str = "general",
    mode: str = "study",
    total_tokens: int = 0,
    total_cost_usd: float = 0.0,
    iteration_count: int = 0,
    tool_calls: list[dict] | None = None,
) -> str:
    """Save current conversation to disk. Returns session ID."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    if isinstance(messages, Session):
        session = messages
        session.save(SESSIONS_DIR)
        return session.id

    now = datetime.now()
    session_id = now.strftime("%Y%m%d_%H%M%S_%f")
    session = Session(
        id=session_id,
        topic=topic,
        mode=mode,
        created_at=now.isoformat(),
        messages=messages,
        total_tokens=total_tokens,
        total_cost_usd=total_cost_usd,
        iteration_count=iteration_count,
        tool_calls=tool_calls or [],
    )
    session.save(SESSIONS_DIR)
    return session_id


def load_session_object(session_id: str) -> Session | None:
    """Load a saved session object by ID."""
    if not re.fullmatch(r"[\w.-]+", session_id):
        raise ValueError(f"Invalid session id: {session_id}")
    base_dir = SESSIONS_DIR.resolve()
    path = (SESSIONS_DIR / f"{session_id}.json").resolve()
    if not path.is_relative_to(base_dir):
        raise ValueError(f"Path traversal detected in session_id: {session_id}")
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    return Session.from_dict(data)


def load_session(session_id: str) -> list[dict] | None:
    """Load a saved session messages by ID."""
    session = load_session_object(session_id)
    if session is None:
        return None
    return session.messages


def list_sessions(limit: int = 10) -> list[dict]:
    """List recent saved sessions."""
    if not SESSIONS_DIR.exists():
        return []

    sessions = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            with open(f) as fh:
                data = json.load(fh)
            session = Session.from_dict(data)
            sessions.append(session.get_summary())
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
