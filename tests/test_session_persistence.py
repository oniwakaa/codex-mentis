"""End-to-end session persistence test: save/load/list/delete, token & cost tracking, backward compatibility."""

import json

import pytest

import pitagora.sessions as sessions_mod
from pitagora.sessions import (
    Session,
    delete_session,
    list_sessions,
    load_session,
    load_session_object,
    save_session,
)


@pytest.fixture(autouse=True)
def tmp_sessions_dir(tmp_path, monkeypatch):
    tmp = tmp_path / "sessions"
    monkeypatch.setattr(sessions_mod, "SESSIONS_DIR", tmp)
    return tmp


def test_save_and_load_round_trip(tmp_sessions_dir):
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    sid = save_session(msgs, topic="limits", mode="study")
    loaded = load_session(sid)
    assert loaded is not None
    assert len(loaded) == 3
    assert loaded[1]["content"] == "hi"


def test_session_record_turn_and_summary(tmp_sessions_dir):
    session = Session(id="test_sess_001", topic="calculus", mode="study")
    session.record_turn(150, 0.005, {"tool": "search", "args": {}})
    session.record_turn(200, 0.010, {"tool": "solve", "args": {}})

    summary = session.get_summary()
    assert summary["total_tokens"] == 350
    assert summary["total_cost_usd"] == pytest.approx(0.015)
    assert summary["iteration_count"] == 2
    assert len(summary["tool_calls"]) == 2

    sid = save_session(session)
    loaded_sess = load_session_object(sid)
    assert loaded_sess is not None
    assert loaded_sess.total_tokens == 350
    assert loaded_sess.total_cost_usd == pytest.approx(0.015)
    assert loaded_sess.iteration_count == 2
    assert len(loaded_sess.tool_calls) == 2


def test_backward_compatibility_old_session_file(tmp_sessions_dir):
    tmp_sessions_dir.mkdir(parents=True, exist_ok=True)
    old_data = {
        "id": "old_session_123",
        "topic": "history",
        "mode": "study",
        "created_at": "2026-01-01T00:00:00",
        "message_count": 1,
        "messages": [{"role": "user", "content": "old query"}],
    }
    file_path = tmp_sessions_dir / "old_session_123.json"
    with open(file_path, "w") as f:
        json.dump(old_data, f)

    loaded_sess = load_session_object("old_session_123")
    assert loaded_sess is not None
    assert loaded_sess.total_tokens == 0
    assert loaded_sess.total_cost_usd == 0.0
    assert loaded_sess.iteration_count == 0
    assert loaded_sess.tool_calls == []
    assert len(loaded_sess.messages) == 1


def test_load_missing_returns_none():
    assert load_session("nope") is None
    assert load_session_object("nope") is None


def test_session_append_and_replay(tmp_sessions_dir):
    sess = Session(id="sess_append_test")
    sess.append("user", "Hello message", extra_key="val")
    assert len(sess.messages) == 1
    assert sess.messages[0]["role"] == "user"
    assert sess.messages[0]["content"] == "Hello message"
    assert sess.messages[0]["extra_key"] == "val"

    replayed = sess.replay()
    assert replayed == sess.messages


def test_session_class_save_load_path(tmp_sessions_dir):
    sess = Session(id="sess_file_test", topic="physics")
    sess.append("user", "What is momentum?")
    file_path = tmp_sessions_dir / "sess_file_test.json"
    sess.save(tmp_sessions_dir)

    loaded = Session.load(file_path)
    assert loaded.id == "sess_file_test"
    assert loaded.session_id == "sess_file_test"
    assert loaded.topic == "physics"
    assert len(loaded.messages) == 1


def test_list_sessions(tmp_sessions_dir):
    save_session([{"role": "user", "content": "a"}], topic="a", mode="study")
    save_session([{"role": "user", "content": "b"}], topic="b", mode="explore")
    listed = list_sessions()
    assert len(listed) == 2
    for s in listed:
        assert "id" in s and "topic" in s and "mode" in s and "message_count" in s
        assert "total_tokens" in s and "total_cost_usd" in s and "iteration_count" in s


def test_delete_session(tmp_sessions_dir):
    sid = save_session([{"role": "user", "content": "x"}], topic="x", mode="study")
    assert delete_session(sid) is True
    assert load_session(sid) is None
    assert delete_session(sid) is False


def test_list_sessions_empty(tmp_sessions_dir):
    assert list_sessions() == []
