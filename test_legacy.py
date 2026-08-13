"""Legacy integration tests — modules referenced here were removed during refactoring.
Kept for reference. Run with: python -m pytest test_legacy.py -v
"""
import pytest

@pytest.mark.skip(reason="Legacy test — references removed modules (math_engine.numerical, knowledge.embeddings, mcp_integration). Rewrite against current API if needed.")
def test_legacy_placeholder():
    pass
