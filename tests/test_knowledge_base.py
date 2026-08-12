import pytest
import os
from pitagora.knowledge.base import KnowledgeBase

def test_knowledge_base_crud(temp_db):
    kb = KnowledgeBase(db_path=temp_db)
    
    # Check stats empty
    stats = kb.get_stats()
    assert stats["documents"] == 0
    assert stats["chunks"] == 0
    
    # Add a document
    chunks = [
        {"text": "Newton's first law says an object stays in motion.", "metadata": {"section": "Newton"}},
        {"text": "Newton's second law is F = ma.", "metadata": {"section": "Newton"}}
    ]
    doc_id = kb.add_document(
        path="/path/to/newton.md",
        title="Newton's Laws",
        subject="physics",
        chunks=chunks,
        metadata={"author": "Newton"}
    )
    assert doc_id > 0
    
    # Check stats updated
    stats = kb.get_stats()
    assert stats["documents"] == 1
    assert stats["chunks"] == 2
    assert stats["subjects"]["physics"] == 1
    
    # List documents
    docs = kb.list_documents()
    assert len(docs) == 1
    assert docs[0]["title"] == "Newton's Laws"
    
    # List by subject
    docs_physics = kb.list_documents(subject="physics")
    assert len(docs_physics) == 1
    docs_math = kb.list_documents(subject="math")
    assert len(docs_math) == 0
    
    # Search document
    results = kb.search("second law", limit=5)
    assert len(results) == 1
    assert "F = ma" in results[0]["content"]
    assert results[0]["source"] == "Newton's Laws"
    assert results[0]["metadata"]["section"] == "Newton"
    
    # Retrieve compatibility alias
    ret_results = kb.retrieve("second law", top_k=5)
    assert len(ret_results) == 1
    
    # Delete document
    assert kb.delete_document("/path/to/newton.md") is True
    assert kb.delete_document("/path/to/newton.md") is False # already deleted
    
    stats_post = kb.get_stats()
    assert stats_post["documents"] == 0
    assert stats_post["chunks"] == 0
