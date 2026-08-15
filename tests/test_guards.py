import time

import pytest

from pitagora.agents.guards import LoopGuard


def test_guard_max_iterations():
    guard = LoopGuard(max_iterations=5)
    assert guard.check_iteration(0) is True
    assert guard.check_iteration(4) is True
    assert guard.check_iteration(5) is False
    assert guard.check_iteration(6) is False


def test_guard_wall_clock_timeout():
    guard = LoopGuard(wall_clock_timeout_s=1)
    assert guard.check_iteration(0) is True
    time.sleep(1.1)
    assert guard.check_iteration(1) is False


def test_guard_cost_budget():
    guard = LoopGuard(max_cost_usd=1.50)
    assert guard.check_cost(0.50) is True
    assert guard.check_cost(1.49) is True
    assert guard.check_cost(1.50) is False
    assert guard.check_cost(2.00) is False


def test_guard_doom_loop_detection():
    guard = LoopGuard()
    resp1 = "Hello world response"
    resp2 = "Different response"

    hash1 = LoopGuard.hash_response(resp1)
    hash2 = LoopGuard.hash_response(resp2)

    assert guard.check_loop_detection("agent_a", hash1) is True
    assert guard.check_loop_detection("agent_a", hash2) is True
    # Duplicate for agent_a -> doom loop!
    assert guard.check_loop_detection("agent_a", hash1) is False
    # Same hash for different agent -> allowed
    assert guard.check_loop_detection("agent_b", hash1) is True


def test_guard_hash_response():
    resp = "Test agent output for hashing"
    h1 = LoopGuard.hash_response(resp)
    h2 = LoopGuard.hash_response(resp)
    assert len(h1) == 16
    assert h1 == h2
    assert h1 != LoopGuard.hash_response("Different output")
