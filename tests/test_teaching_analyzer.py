"""Tests for the ResponseAnalyzer (TASK 2)."""
import json

from pitagora.teaching.analyzer import (
    ResponseAnalyzer, ResponseClassification, Classification, DELTA,
)


def _make_chat(reply_obj):
    """Return a fake chat_completion fn that yields the given decoded object."""
    def fake(messages, model=None, config=None):
        return json.dumps(reply_obj)
    return fake


def test_shortcut_bypasses_llm():
    a = ResponseAnalyzer(_make_chat({"label": "correct"}))
    r = a.classify("n", "limits", "definition")
    assert r.via_shortcut is True
    assert r.label == "skip"
    assert r.delta == DELTA["skip"]


def test_shortcut_question_mark():
    a = ResponseAnalyzer(_make_chat({"label": "correct"}))
    r = a.classify("?", "limits", "definition")
    assert r.via_shortcut is True
    assert r.label == "confused"


def test_correct_classification():
    a = ResponseAnalyzer(_make_chat({"label": "correct", "rationale": "nailed it"}))
    r = a.classify("The limit is the approached value.", "limits", "definition")
    assert r.label == "correct"
    assert r.delta == 0.15
    assert r.via_shortcut is False
    assert "nailed" in r.rationale


def test_partial_classification():
    a = ResponseAnalyzer(_make_chat({"label": "partial"}))
    r = a.classify("kind of right", "limits", "definition")
    assert r.label == "partial"
    assert r.delta == 0.05


def test_fenced_json_parsed():
    def fenced(messages, model=None, config=None):
        return "```json\n" + json.dumps({"label": "confused"}) + "\n```"
    a = ResponseAnalyzer(fenced)
    r = a.classify("huh?", "limits", "definition")
    assert r.label == "confused"
    assert r.delta == -0.20


def test_unknown_label_falls_back_to_partial():
    a = ResponseAnalyzer(_make_chat({"label": "banana"}))
    r = a.classify("x", "limits", "definition")
    assert r.label == "partial"
    assert r.delta == 0.05


def test_unparseable_salvages_bare_label():
    def broken(messages, model=None, config=None):
        return "The reply shows the learner is confused about it."
    a = ResponseAnalyzer(broken)
    r = a.classify("x", "limits", "definition")
    assert r.label == "confused"


def test_unparseable_total_fallback():
    def broken(messages, model=None, config=None):
        return "???notjson???"
    a = ResponseAnalyzer(broken)
    r = a.classify("x", "limits", "definition")
    assert r.label == "partial"


def test_llm_exception_returns_partial():
    def boom(messages, model=None, config=None):
        raise RuntimeError("network down")
    a = ResponseAnalyzer(boom)
    r = a.classify("a real answer", "limits", "definition")
    assert r.label == "partial"
    assert r.delta == 0.05
    assert "analyzer_error" in r.rationale


def test_all_classifications_have_deltas():
    for label in Classification:
        assert label.value in DELTA
