"""
Tick-based action scheduler.
Divides citizens into N fixed batches, one per tick.
Guarantees every citizen gets a full reasoning cycle within
B = ceil(1 / CITIZEN_REASONING_RATE) ticks.
"""

import math
from typing import List, Set, Dict, Any
from collections import Counter

from autosociety.backend.core.config import world_config as cfg


class ActionScheduler:
    """
    Schedules which citizens get a full reasoning cycle each tick.
    Uses fixed batched round-robin guaranteed coverage.

    Coverage guarantee: every citizen gets at least one full reasoning
    cycle within any rolling window of B = ceil(1 / CITIZEN_REASONING_RATE)
    ticks. At CITIZEN_REASONING_RATE=0.45, B=3.
    """

    def __init__(self, total_citizens: int):
        self.total = total_citizens
        self._num_batches = max(2, round(1 / cfg.CITIZEN_REASONING_RATE))
        self._batch_size = math.ceil(total_citizens / self._num_batches)
        self._tick = 0
        self._tick_history: List[Set[int]] = []

        # Build fixed batches covering all citizens
        self._batches: List[Set[int]] = []
        all_ids = list(range(1, total_citizens + 1))
        for b in range(self._num_batches):
            start = b * self._batch_size
            end = min(start + self._batch_size, total_citizens)
            self._batches.append(set(all_ids[start:end]))

    @property
    def citizens_per_tick(self) -> int:
        return self._batch_size

    @property
    def current_tick(self) -> int:
        return self._tick

    @property
    def history(self) -> List[Set[int]]:
        return list(self._tick_history)

    @property
    def num_batches(self) -> int:
        return self._num_batches

    def tick(self) -> Set[int]:
        """
        Advance one tick. Return set of citizen IDs that should
        get a full reasoning cycle this tick.
        """
        self._tick += 1
        batch_idx = (self._tick - 1) % self._num_batches
        selected = self._batches[batch_idx]
        self._tick_history.append(selected)
        return selected

    def citizens_for_lightweight_update(self, reasoning_set: Set[int]) -> Set[int]:
        """Return citizens that get a lightweight (no LLM) update."""
        all_citizens = set(range(1, self.total + 1))
        return all_citizens - reasoning_set

    def verify_rolling_window(self, num_ticks: int) -> Dict[str, Any]:
        """
        Run `num_ticks` forward ticks and verify every citizen is covered
        within any max_window-sized window.
        Returns pass/fail + gap analysis.
        """
        self._tick = 0
        self._tick_history = []
        for _ in range(num_ticks):
            self.tick()

        max_window = self._num_batches
        issues: Dict[int, int] = {}
        gap_counts: Dict[int, int] = {}

        for cid in range(1, self.total + 1):
            last_seen = -1
            max_gap = 0
            for t in range(num_ticks):
                if cid in self._tick_history[t]:
                    gap = t - last_seen
                    if gap > max_gap:
                        max_gap = gap
                    gap_counts[gap] = gap_counts.get(gap, 0) + 1
                    last_seen = t

            if max_gap > max_window:
                issues[cid] = max_gap

        return {
            "passed": len(issues) == 0,
            "total_ticks": num_ticks,
            "citizens": self.total,
            "batches": self._num_batches,
            "batch_size": self._batch_size,
            "max_allowed_gap": max_window,
            "violations": issues,
            "gap_counts": dict(sorted(gap_counts.items())),
        }
