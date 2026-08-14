"""End-to-end session persistence test (TASK 6): save/load/list/delete."""

import pytest

import pitagora.sessions as sessions_mod
from pitagora.sessions import delete_session, list_sessions, load_session, save_session


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


def test_load_missing_returns_none():
    assert load_session("nope") is None


def test_list_sessions(tmp_sessions_dir):
    save_session([{"role": "user", "content": "a"}], topic="a", mode="study")
    save_session([{"role": "user", "content": "b"}], topic="b", mode="explore")
    listed = list_sessions()
    assert len(listed) == 2
    for s in listed:
        assert "id" in s and "topic" in s and "mode" in s and "message_count" in s


def test_delete_session(tmp_sessions_dir):
    sid = save_session([{"role": "user", "content": "x"}], topic="x", mode="study")
    assert delete_session(sid) is True
    assert load_session(sid) is None
    assert delete_session(sid) is False


def test_list_sessions_empty(tmp_sessions_dir):
    assert list_sessions() == []
