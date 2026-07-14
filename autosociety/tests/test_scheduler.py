"""
Tests for ActionScheduler — verifies rolling-window guarantee.
"""

import pytest
import math
from unittest.mock import patch, MagicMock
from collections import defaultdict

from autosociety.backend.core.scheduler import ActionScheduler
from autosociety.backend.core.config import world_config as cfg


class TestActionScheduler:
    def test_creates_with_correct_count(self):
        sched = ActionScheduler(40)
        # Batch-based: num_batches = round(1/0.45)=2, batch_size = ceil(40/2)=20
        num_batches = max(2, round(1 / cfg.CITIZEN_REASONING_RATE))
        expected_batch_size = math.ceil(40 / num_batches)
        assert sched.citizens_per_tick == expected_batch_size

    def test_single_tick_returns_subset(self):
        sched = ActionScheduler(40)
        selected = sched.tick()
        assert len(selected) == sched.citizens_per_tick
        assert all(1 <= cid <= 40 for cid in selected)

    def test_multiple_ticks_different_subsets(self):
        sched = ActionScheduler(40)
        t1 = sched.tick()
        t2 = sched.tick()
        assert t1 != t2

    def test_all_citizens_eventually_scheduled(self):
        sched = ActionScheduler(40)
        all_selected = set()
        for _ in range(sched.num_batches * 2):
            all_selected |= sched.tick()
        assert len(all_selected) == 40

    def test_rolling_window_guarantee_10_ticks(self):
        sched = ActionScheduler(40)
        max_allowed = sched.num_batches  # scheduler's own coverage window

        history = []
        for _ in range(10):
            history.append(sched.tick())

        for cid in range(1, 41):
            last_seen = -1
            for t, tick_set in enumerate(history):
                if cid in tick_set:
                    gap = t - last_seen
                    assert gap <= max_allowed, (
                        f"Citizen {cid} had gap of {gap} ticks "
                        f"(max allowed: {max_allowed})"
                    )
                    last_seen = t

    def test_rolling_window_with_30_citizens(self):
        sched = ActionScheduler(30)
        max_allowed = sched.num_batches

        history = []
        for _ in range(10):
            history.append(sched.tick())

        for cid in range(1, 31):
            last_seen = -1
            for t, tick_set in enumerate(history):
                if cid in tick_set:
                    gap = t - last_seen
                    assert gap <= max_allowed
                    last_seen = t

    def test_lightweight_set_complement(self):
        sched = ActionScheduler(10)
        selected = sched.tick()
        lightweight = sched.citizens_for_lightweight_update(selected)
        assert len(selected) + len(lightweight) == 10
        assert selected & lightweight == set()

    def test_verify_rolling_window_method(self):
        sched = ActionScheduler(40)
        result = sched.verify_rolling_window(10)
        assert result["passed"] is True
        assert len(result["violations"]) == 0
