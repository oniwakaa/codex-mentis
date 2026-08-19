"""Tests for Spaced Repetition and Concept Graph Exporters."""

import json
from pitagora.concepts.graph import ConceptGraph
from pitagora.concepts.export import export_graph_to_mermaid, export_graph_to_canvas
from pitagora.memory.export import export_deck_to_anki, export_deck_to_markdown
from pitagora.memory.store import MemoryStore
from pitagora.memory.spaced_repetition import SpacedRepetition


def test_mermaid_graph_export():
    graph = ConceptGraph()
    mastery = {"alg_groups": 1.0, "calc_limits": 0.5}
    mmd = export_graph_to_mermaid(graph, mastery)

    assert "flowchart TD" in mmd
    assert "classDef mastered" in mmd
    assert "Groups" in mmd
    assert "Limits" in mmd


def test_canvas_graph_export(tmp_path):
    graph = ConceptGraph()
    dest = str(tmp_path / "test_graph.canvas")
    count = export_graph_to_canvas(graph, dest, {"alg_groups": 0.9})

    assert count > 0
    with open(dest, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == count


def test_anki_and_markdown_deck_exports(tmp_path):
    db_path = str(tmp_path / "test_export.db")
    sr = SpacedRepetition(db_path=db_path)
    mem = MemoryStore(db_path=db_path)

    sr.schedule_review("Quantum Mechanics", quality=4)
    mem.record_misconception("Physics", "Quantum Mechanics", "Wavefunction collapse is physical", "It is an epistemic state update")

    anki_path = str(tmp_path / "deck.tsv")
    md_path = str(tmp_path / "deck.md")

    anki_count = export_deck_to_anki(anki_path, db_path=db_path)
    assert anki_count >= 2
    with open(anki_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Quantum Mechanics" in content

    md_count = export_deck_to_markdown(md_path, db_path=db_path)
    assert md_count >= 2
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    assert "# Pitagora Spaced Repetition Deck" in md_content
    assert "#flashcard" in md_content
