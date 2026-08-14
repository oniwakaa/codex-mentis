import pytest

from pitagora.knowledge.chunker import SmartChunker


def test_smart_chunker_basic():
    chunker = SmartChunker(max_chunk_size=100, min_chunk_size=10, overlap=10)

    text = """
# Physics 101
First paragraph of general introduction.

## Kinematics
Kinematics is the study of motion. We analyze position, velocity, and acceleration.
$$v = \\frac{dx}{dt}$$
Velocity is derivative of position.
    """

    chunks = chunker.chunk_text(text, source="kinematics.md")

    assert len(chunks) > 0
    # The header title should be parsed correctly
    assert chunks[0]["metadata"]["source"] == "kinematics.md"
    assert "Physics 101" in [c["metadata"]["section"] for c in chunks]
    assert "Kinematics" in [c["metadata"]["section"] for c in chunks]


def test_smart_chunker_equation_preservation():
    chunker = SmartChunker(max_chunk_size=150, min_chunk_size=20, overlap=10)

    text = """
We present the fundamental relation:
$$E = m c^2$$
This formula relates energy E, mass m, and light speed c.
    """

    chunks = chunker.chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["has_equation"] is True


def test_get_overlap_text():
    chunker = SmartChunker(overlap=30)
    text = "This is sentence one. This is sentence two. This is sentence three."
    overlap = chunker._get_overlap_text(text)
    assert "sentence three." in overlap


def test_chunk_equation_block():
    chunker = SmartChunker()
    text = "Define force:\n$$F = ma$$\nHere F is force, m is mass, a is acceleration."

    chunks = chunker.chunk_equation_block(text)
    assert len(chunks) >= 1
    # Check that equation and explanation are merged
    assert "F = ma" in chunks[0]["text"]
    assert "Here F is force" in chunks[0]["text"]
