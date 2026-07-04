"""Generic health-tracked pool of candidates (proxies, SearX instances, etc.)."""

import random
from typing import Callable, Generic, Optional, TypeVar

T = TypeVar("T")


class HealthTrackedPool(Generic[T]):
    """Tracks which candidates in a pool are currently reachable.

    Probes candidates lazily (only when no known-working ones remain) via an
    injected probe function, and remembers dead candidates so they aren't
    retried within the same run.
    """

    def __init__(
        self,
        candidates: list[T],
        probe: Callable[[T], bool],
        probe_sample_size: int = 5,
    ):
        self.candidates = candidates
        self._probe = probe
        self._probe_sample_size = probe_sample_size
        self._working: list[T] = []
        self._dead: set[T] = set()

    def get_working(self) -> list[T]:
        """Return candidates known to be reachable, probing more if needed."""
        if self._working:
            return self._working

        remaining = [c for c in self.candidates if c not in self._dead]
        sample = random.sample(remaining, min(self._probe_sample_size, len(remaining)))
        for candidate in sample:
            if self._probe(candidate):
                self._working.append(candidate)

        return self._working

    def pick(self) -> Optional[T]:
        """Pick a random known-working candidate, or None if none are available."""
        working = self.get_working()
        if not working:
            return None
        return random.choice(working)

    def mark_dead(self, candidate: T):
        """Remove a candidate from the working set and blacklist it for this run."""
        if candidate in self._working:
            self._working.remove(candidate)
        self._dead.add(candidate)
