"""Tests for the ResponseAnalyzer (TASK 2)."""

import json

from pitagora.teaching.analyzer import (
    DELTA,
    Classification,
    ResponseAnalyzer,
)


def _make_chat(reply_obj):
    """Return a fake chat_completion fn that yields the given decoded object."""

    def fake(messages, model=None, config=None):
        return json.dumps(reply_obj)

    return fake


def test_shortcut_bypasses_llm():
    a = ResponseAnalyzer(_make_chat({"label": "correct"}))
    r = a.classify("s", "limits", "definition")
    assert r.via_shortcut is True
    assert r.label == "skip"
    assert r.delta == DELTA["skip"]


def test_shortcut_question_mark():
    a = ResponseAnalyzer(_make_chat({"label": "correct"}))
    r = a.classify("?", "limits", "definition")
    assert r.via_shortcut is True
    assert r.label == "confused"


def test_teaching_control_shortcuts_bypass_llm():
    def fail_if_called(messages, model=None, config=None):
        raise AssertionError("shortcut should not call the LLM")

    analyzer = ResponseAnalyzer(fail_if_called)
    expected = {
        "n": "skip",
        "e": "different_style",
        "d": "deeper",
        "v": "visualize",
        "q": "quiz",
    }

    for shortcut, label in expected.items():
        result = analyzer.classify(shortcut, "limits", "definition")
        assert result.via_shortcut is True
        assert result.label == label


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


def test_different_style_is_a_canonical_classification():
    assert Classification.different_style.value == "different_style"
    assert DELTA["different_style"] == 0.0

    result = ResponseAnalyzer._parse(
        '{"label": "different_style", "rationale": "The explanation style did not land."}'
    )
    assert result.label == "different_style"
