"""Legacy system tests — memory.layers module was removed.
Kept for reference. Run with: python -m pytest test_system_legacy.py -v
"""
import pytest

@pytest.mark.skip(reason="Legacy test — references removed module memory.layers. Rewrite against current API if needed.")
def test_legacy_system_placeholder():
    pass
