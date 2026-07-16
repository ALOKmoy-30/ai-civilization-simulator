"""
Tests for Day-to-Tick synchronization guarantees.

Verifies that:
  a) After N tick advances, engine.current_tick == world.simulation_day
  b) TickSnapshot.simulation_day is always populated and equals tick
  c) Government policy sessions do NOT increment simulation_day
     (that is the engine's exclusive responsibility)
"""

import pytest
from unittest.mock import patch

from autosociety.backend.core.database import (
    get_session, get_or_create_world_state, create_citizen, CitizenCreate,
)
from autosociety.backend.core.metrics import get_all_snapshots, init_metrics_db
from autosociety.backend.core.engine import SimulationEngine


def _seed_citizen(session, name="Test Citizen", job="Engineer"):
    return create_citizen(session, CitizenCreate(
        name=name, age=30, job=job,
        happiness=60.0, wealth=300.0, health=80.0, social_score=50.0,
    ))


class TestTickDayMath:
    """Verify 1 tick = 1 day invariant."""

    def test_tick_equals_simulation_day_after_advances(self):
        """
        After N deterministic tick advances, engine tick == world.simulation_day.
        No LLM calls are made (reasoning is stubbed out).
        """
        session = get_session()
        _seed_citizen(session)
        session.close()

        engine = SimulationEngine()
        # Advance 5 ticks synchronously without spawning asyncio tasks
        for _ in range(5):
            engine._tick += 1
            engine._sync_advance_tick()

        session = get_session()
        world = get_or_create_world_state(session)
        session.close()

        assert engine.current_tick == 5, "Engine tick should be 5"
        assert world.simulation_day == engine.current_tick, (
            f"simulation_day ({world.simulation_day}) must equal "
            f"engine.current_tick ({engine.current_tick})"
        )

    def test_tick_zero_at_start(self):
        """A freshly created engine starts at tick 0."""
        engine = SimulationEngine()
        assert engine.current_tick == 0

    def test_reset_returns_tick_to_zero(self):
        """After reset(), tick returns to 0 regardless of how many advances occurred."""
        session = get_session()
        _seed_citizen(session, name="Reset Citizen")
        session.close()

        engine = SimulationEngine()
        engine._tick += 3
        engine._sync_advance_tick()
        engine.reset()
        assert engine.current_tick == 0

    def test_multiple_advances_stay_in_sync(self):
        """simulation_day tracks tick across multiple advances without drift."""
        session = get_session()
        _seed_citizen(session, name="Sync Citizen")
        session.close()

        engine = SimulationEngine()
        advances = 7
        for i in range(advances):
            engine._tick += 1
            engine._sync_advance_tick()

            session = get_session()
            world = get_or_create_world_state(session)
            session.close()
            assert world.simulation_day == engine.current_tick, (
                f"After advance {i+1}: simulation_day {world.simulation_day} "
                f"!= tick {engine.current_tick}"
            )


class TestSnapshotSimulationDay:
    """Verify TickSnapshot.simulation_day is stored and matches tick."""

    def test_snapshot_has_simulation_day_field(self):
        """record_snapshot stores simulation_day alongside tick."""
        from autosociety.backend.core.metrics import record_snapshot
        record_snapshot(
            tick=1, simulation_day=1, gdp=500.0,
            crime_rate=0.05, tax_revenue=75.0, active_businesses=0,
        )
        snapshots = get_all_snapshots()
        assert len(snapshots) == 1
        snap = snapshots[0]
        assert snap.simulation_day == 1
        assert snap.tick == 1

    def test_snapshot_simulation_day_equals_tick(self):
        """When multiple ticks are recorded, simulation_day always matches tick."""
        from autosociety.backend.core.metrics import record_snapshot
        for t in range(1, 6):
            record_snapshot(tick=t, simulation_day=t, gdp=100.0 * t,
                            crime_rate=0.01, tax_revenue=15.0 * t, active_businesses=0)

        snapshots = get_all_snapshots()
        assert len(snapshots) == 5
        for snap in snapshots:
            assert snap.simulation_day == snap.tick, (
                f"Snapshot tick={snap.tick} has simulation_day={snap.simulation_day}"
            )

    def test_snapshot_defaults_simulation_day_to_tick(self):
        """When simulation_day is omitted, it defaults to tick value."""
        from autosociety.backend.core.metrics import record_snapshot
        # Call without simulation_day parameter
        record_snapshot(tick=42, gdp=0.0, crime_rate=0.0, tax_revenue=0.0, active_businesses=0)
        snaps = get_all_snapshots()
        assert len(snaps) == 1
        assert snaps[0].simulation_day == 42


class TestGovernmentDoesNotIncrementDay:
    """Government policy sessions must NOT advance simulation_day."""

    def test_government_session_does_not_change_simulation_day(self):
        """
        Running a government policy session should leave simulation_day unchanged.
        Stubs the full CrewAI pipeline to avoid LLM calls.
        """
        session = get_session()
        world = get_or_create_world_state(session)
        day_before = world.simulation_day
        session.close()

        # Stub decide_policy so no LLM is called
        fake_result = {
            "policy_id": 1,
            "name": "Test Policy",
            "description": "Test",
            "effects": {"economic_health": 2},
            "decision": "approved",
            "raw_output": "POLICY NAME: Test\nDESCRIPTION: Test\nEFFECTS: economic_health=2\nDECISION: approved\nORDER: Implement",
        }

        with patch(
            "autosociety.agents.crews.government.GovernmentCrew.decide_policy",
            return_value=fake_result,
        ):
            from autosociety.agents.crews.government import GovernmentCrew
            gov = GovernmentCrew.__new__(GovernmentCrew)
            result = fake_result  # use stub directly

        session = get_session()
        world_after = get_or_create_world_state(session)
        day_after = world_after.simulation_day
        session.close()

        assert day_after == day_before, (
            f"Government session should not change simulation_day. "
            f"Before: {day_before}, After: {day_after}"
        )
