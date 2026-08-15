import hashlib
import time
from dataclasses import dataclass, field


@dataclass
class LoopGuard:
    """Safety guards for agent execution loops."""

    max_iterations: int = 25
    max_cost_usd: float = 2.0
    wall_clock_timeout_s: int = 300
    _seen_fingerprints: set[str] = field(default_factory=set)
    _start_time: float = field(default_factory=time.monotonic)

    def check_iteration(self, iteration: int) -> bool:
        """Returns True if the loop should continue, False if it should stop."""
        if iteration >= self.max_iterations:
            return False
        if time.monotonic() - self._start_time > self.wall_clock_timeout_s:
            return False
        return True

    def check_cost(self, total_cost_usd: float) -> bool:
        """Returns True if within budget, False if exceeded."""
        return total_cost_usd < self.max_cost_usd

    def check_loop_detection(self, agent_name: str, response_hash: str) -> bool:
        """Returns True if this is a NEW response (not a doom-loop), False if repeated."""
        fingerprint = f"{agent_name}:{response_hash}"
        if fingerprint in self._seen_fingerprints:
            return False  # Doom loop detected
        self._seen_fingerprints.add(fingerprint)
        return True

    @staticmethod
    def hash_response(response: str) -> str:
        """Create a fingerprint of an agent response for loop detection."""
        return hashlib.sha256(response.encode()).hexdigest()[:16]
