import json
import os
from datetime import datetime

import pytest

from pitagora.core.models import MemoryEntry
from pitagora.memory.store import MemoryStore, cosine_similarity
from tests.conftest import MockProvider


def test_cosine_similarity():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 1.0], [1.0, 1.0]) == pytest.approx(1.0)


def test_memory_store_basic_crud(temp_db):
    store = MemoryStore(db_path=temp_db)

    # 1. Create
    entry = MemoryEntry(
        layer="L2",
        content="Newton's laws of motion are three physical laws.",
        topic="physics",
        metadata={"author": "Newton"},
        timestamp=datetime(2026, 8, 12, 12, 0, 0),
    )

    entry_id = store.create_memory_entry(entry)
    assert entry_id > 0

    # 2. Read
    fetched = store.get_memory_entry(entry_id)
    assert fetched is not None
    assert fetched.layer == "L2"
    assert fetched.content == "Newton's laws of motion are three physical laws."
    assert fetched.topic == "physics"
    assert fetched.metadata == {"author": "Newton"}
    assert fetched.timestamp.strftime("%Y-%m-%d %H:%M:%S") == "2026-08-12 12:00:00"

    # 3. Update
    fetched.content = "Newton's laws are classical mechanics foundation."
    fetched.metadata = {"author": "Newton", "verified": True}
    assert store.update_memory_entry(entry_id, fetched) is True

    updated = store.get_memory_entry(entry_id)
    assert updated.content == "Newton's laws are classical mechanics foundation."
    assert updated.metadata["verified"] is True

    # 4. List
    all_mem = store.list_memories(layer="L2", topic="physics")
    assert len(all_mem) == 1
    assert all_mem[0].content == updated.content

    # 5. Delete
    assert store.delete_memory_entry(entry_id) is True
    assert store.get_memory_entry(entry_id) is None


def test_memory_store_semantic_retrieve(temp_db):
    store = MemoryStore(db_path=temp_db)

    # Save a few entries
    store.save("L2", "The derivative of x^2 is 2x.", "calculus")
    store.save("L3", "Quantum mechanics states particles have wave behavior.", "physics")

    # Semantic retrieve (uses mock or tfidf vectorizer)
    res = store.retrieve("wave function mechanics", top_k=2)
    assert len(res) == 2
    # The QM entry should be more similar/ranked first
    assert "Quantum" in res[0]["content"]


def test_save_get_conversation(temp_db):
    store = MemoryStore(db_path=temp_db)

    messages = [
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "How can I help you today?"},
    ]
    store.save_conversation("conv_123", "greeting", messages)

    fetched = store.get_conversation("conv_123")
    assert fetched == messages

    assert store.get_conversation("nonexistent") is None


def test_promote_and_synthesize(temp_db, mock_provider):
    store = MemoryStore(db_path=temp_db)

    # Setup conversation
    messages = [
        {"role": "user", "content": "Let's study calculus."},
        {"role": "assistant", "content": "The derivative is the rate of change."},
    ]
    store.save_conversation("conv_calc", "Calculus Intro", messages)

    # Promote L1 -> L2
    mock_provider.responses.append(
        {"content": "Promoted summary: derivative is rate of change", "tool_calls": []}
    )

    entry_id = store.promote_l1_to_l2("conv_calc", provider=mock_provider)
    assert entry_id is not None

    l2_mem = store.get_memory_entry(entry_id)
    assert l2_mem.layer == "L2"
    assert "Promoted summary" in l2_mem.content

    # Synthesize L2 -> L3
    mock_provider.responses.append(
        {"content": "Synthesized calculus insights across topics", "tool_calls": []}
    )

    l3_entry_id = store.synthesize_l2_to_l3(["Calculus Intro"], provider=mock_provider)
    assert l3_entry_id is not None

    l3_mem = store.get_memory_entry(l3_entry_id)
    assert l3_mem.layer == "L3"
    assert "Synthesized calculus" in l3_mem.content


def test_backup_and_export(temp_db, tmp_path):
    store = MemoryStore(db_path=temp_db)
    store.save("L2", "Content to export", "topic")

    backup_file = str(tmp_path / "backup.db")
    export_file = str(tmp_path / "export.json")

    assert store.backup_database(backup_file) is True
    assert os.path.exists(backup_file)

    assert store.export_memories(export_file) is True
    assert os.path.exists(export_file)

    with open(export_file) as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["content"] == "Content to export"


def test_learner_facts_and_misconceptions(temp_db):
    store = MemoryStore(db_path=temp_db)

    # 1. Learner facts
    store.record_learner_fact("explanation_style", "concise", category="preference")
    store.record_learner_fact("level", "advanced", category="skill")
    facts = store.get_learner_facts()
    assert facts["explanation_style"] == "concise"
    assert facts["level"] == "advanced"

    pref_facts = store.get_learner_facts(category="preference")
    assert "explanation_style" in pref_facts
    assert "level" not in pref_facts

    # 2. Misconceptions
    m_id = store.record_misconception(
        topic="quantum_mechanics",
        concept="wavefunction_collapse",
        misconception="Believes collapse is an instantaneous physical signal violation of SR",
    )
    assert m_id > 0

    unresolved = store.get_misconceptions(topic="quantum_mechanics", unresolved_only=True)
    assert len(unresolved) == 1
    assert unresolved[0]["concept"] == "wavefunction_collapse"
    assert unresolved[0]["resolved"] is False

    # Snapshot check
    snapshot = store.get_learner_snapshot(topic="quantum_mechanics")
    assert "explanation_style" in snapshot
    assert "wavefunction_collapse" in snapshot

    # Resolve misconception
    assert store.resolve_misconception(m_id, resolution="Decoherence explains pointer states") is True
    unresolved_after = store.get_misconceptions(topic="quantum_mechanics", unresolved_only=True)
    assert len(unresolved_after) == 0

