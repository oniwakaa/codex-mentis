"""Legacy feature tests — memory.layers and memory.retrieval modules were removed.
Kept for reference. Run with: python -m pytest test_new_features_legacy.py -v
"""
import pytest

@pytest.mark.skip(reason="Legacy test — references removed modules (memory.layers, memory.retrieval). Rewrite against current API if needed.")
def test_legacy_features_placeholder():
    pass
