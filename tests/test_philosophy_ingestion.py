"""Tests for philosophy knowledge acquisition (SEP, Classic Texts)."""

from unittest.mock import MagicMock
from pitagora.knowledge.acquisition import KnowledgeAcquisition


def test_search_philosophy_mock():
    acq = KnowledgeAcquisition()
    acq.webfetch = MagicMock()
    acq.webfetch.search.return_value = [
        {"title": "Epistemology (Stanford Encyclopedia of Philosophy)", "url": "https://plato.stanford.edu/entries/epistemology/", "snippet": "Epistemology is the study of knowledge."}
    ]

    results = acq.search_philosophy("epistemology", max_results=3)
    assert len(results) >= 1
    assert "plato.stanford.edu" in results[0]["url"]


def test_fetch_sep_entry_mock():
    acq = KnowledgeAcquisition()
    acq.webfetch = MagicMock()
    acq.webfetch.fetch_url.return_value = {
        "title": "Modal Logic",
        "url": "https://plato.stanford.edu/entries/logic-modal/",
        "text": "Modal logic is a type of formal logic.\n\n# 1. First Section\nDetails about possible worlds semantics.",
    }

    entry = acq.fetch_sep_entry("logic-modal")
    assert entry["source_type"] == "sep_philosophy"
    assert "Modal logic" in entry["preamble"]
    assert entry["title"] == "Modal Logic"


def test_fetch_classic_text_mock():
    acq = KnowledgeAcquisition()
    acq.webfetch = MagicMock()
    acq.webfetch.fetch_url.return_value = {
        "title": "Ethics by Benedict de Spinoza",
        "url": "https://www.gutenberg.org/files/3800/3800-0.txt",
        "text": "PART I. CONCERNING GOD. DEFINITIONS. I. By that which is self-caused...",
    }

    res = acq.fetch_classic_text("Spinoza Ethics", gutenberg_id=3800)
    assert res["source_type"] == "classic_text"
    assert "CONCERNING GOD" in res["excerpt"]
