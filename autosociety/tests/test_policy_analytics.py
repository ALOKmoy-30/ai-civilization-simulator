"""
Tests for Policy analytics data integrity.

Verifies:
  a) Policies are stored with enacted_day, reasoning_summary, decision_status
  b) Policy effects field is valid JSON (not Python repr)
  c) The /queries/policies endpoint returns enriched PolicyResponse objects
  d) The /queries/analytics/historical and /queries/backups endpoints function correctly
"""

import json
import pytest
from fastapi.testclient import TestClient

from autosociety.backend.core.database import (
    get_session, create_citizen, CitizenCreate,
    create_policy, PolicyCreate, list_policies,
)


def _seed_citizen(n=1):
    session = get_session()
    for i in range(n):
        create_citizen(session, CitizenCreate(
            name=f"Policy Test Citizen {i}",
            age=30, job="Engineer",
            happiness=60.0, wealth=300.0, health=80.0, social_score=50.0,
        ))
    session.close()


def _make_client():
    """Build a TestClient with a fresh SimulationEngine."""
    from autosociety.backend.core.engine import SimulationEngine
    from autosociety.backend.routers import simulation
    from autosociety.backend.main import app
    eng = SimulationEngine()
    simulation.set_engine(eng)
    return TestClient(app)


class TestPolicyStorageFields:
    """Verify new policy columns are persisted correctly."""

    def test_policy_stores_enacted_day(self):
        """PolicyCreate with enacted_day stores the value in the DB."""
        session = get_session()
        policy = create_policy(session, PolicyCreate(
            name="Day Test Policy",
            description="A policy enacted on day 5",
            effects=json.dumps({"economic_health": 3}),
            enacted_day=5,
            decision_status="approved",
        ))
        policy_id = policy.id
        session.close()

        session = get_session()
        from autosociety.backend.core.database import get_policy
        loaded = get_policy(session, policy_id)
        session.close()

        assert loaded is not None
        assert loaded.enacted_day == 5

    def test_policy_stores_reasoning_summary(self):
        """reasoning_summary text is persisted to the DB."""
        reasoning = "POLICY NAME: Test\nDESCRIPTION: Test\nORDER: Implement"
        session = get_session()
        policy = create_policy(session, PolicyCreate(
            name="Reasoning Test Policy",
            description="Has a reasoning summary",
            effects=json.dumps({"avg_happiness": 2}),
            reasoning_summary=reasoning,
            enacted_day=10,
        ))
        policy_id = policy.id
        session.close()

        session = get_session()
        from autosociety.backend.core.database import get_policy
        loaded = get_policy(session, policy_id)
        session.close()

        assert loaded.reasoning_summary == reasoning

    def test_policy_stores_decision_status(self):
        """decision_status is persisted and defaults to 'approved'."""
        session = get_session()
        policy_approved = create_policy(session, PolicyCreate(
            name="Approved Policy",
            description="Gets approved",
            effects="{}",
            decision_status="approved",
        ))
        policy_modified = create_policy(session, PolicyCreate(
            name="Modified Policy",
            description="Gets modified",
            effects="{}",
            decision_status="modified",
        ))
        # Read IDs before closing session to avoid DetachedInstanceError
        approved_id = policy_approved.id
        modified_id = policy_modified.id
        session.close()

        session = get_session()
        from autosociety.backend.core.database import get_policy
        loaded_a = get_policy(session, approved_id)
        loaded_m = get_policy(session, modified_id)
        session.close()

        assert loaded_a.decision_status == "approved"
        assert loaded_m.decision_status == "modified"

    def test_policy_effects_is_valid_json(self):
        """
        Effects stored by government.py should be valid JSON, not Python repr.
        """
        effects_dict = {"economic_health": 5, "avg_happiness": -2, "political_stability": 3}
        session = get_session()
        policy = create_policy(session, PolicyCreate(
            name="JSON Effects Policy",
            description="Tests JSON serialization",
            effects=json.dumps(effects_dict),
        ))
        policy_id = policy.id
        session.close()

        session = get_session()
        from autosociety.backend.core.database import get_policy
        loaded = get_policy(session, policy_id)
        session.close()

        # Must be parseable as JSON (not Python repr like "{'key': 1}")
        parsed = json.loads(loaded.effects)
        assert parsed == effects_dict

    def test_policy_default_fields_when_not_provided(self):
        """Policy without optional fields should use sensible defaults."""
        session = get_session()
        policy = create_policy(session, PolicyCreate(
            name="Minimal Policy",
            description="No extras",
            effects="{}",
        ))
        session.close()

        assert policy.decision_status == "approved"
        assert policy.enacted_day is None
        assert policy.reasoning_summary is None


class TestPoliciesAPIEndpoint:
    """Verify /queries/policies returns enriched data."""

    def test_policies_endpoint_returns_new_fields(self):
        """PolicyResponse includes effects_parsed, enacted_day, reasoning_summary."""
        _seed_citizen()
        session = get_session()
        create_policy(session, PolicyCreate(
            name="API Test Policy",
            description="For API testing",
            effects=json.dumps({"economic_health": 4, "avg_happiness": -1}),
            reasoning_summary="Governor ORDER: Full Implementation",
            enacted_day=7,
            decision_status="approved",
        ))
        session.close()

        client = _make_client()
        r = client.get("/queries/policies")
        assert r.status_code == 200
        policies = r.json()
        assert len(policies) >= 1

        policy = next((p for p in policies if p["name"] == "API Test Policy"), None)
        assert policy is not None, "Policy not found in response"

        # Verify new fields
        assert policy.get("enacted_day") == 7
        assert policy.get("decision_status") == "approved"
        assert policy.get("reasoning_summary") == "Governor ORDER: Full Implementation"
        assert "effects_parsed" in policy
        parsed = policy["effects_parsed"]
        assert parsed.get("economic_health") == 4
        assert parsed.get("avg_happiness") == -1

    def test_policies_endpoint_handles_legacy_effects(self):
        """
        Policies with Python repr effects (legacy format) are gracefully parsed.
        _parse_policy_effects should handle both JSON and Python dict repr.
        """
        _seed_citizen(n=2)
        session = get_session()
        # Simulate legacy format: Python repr string
        create_policy(session, PolicyCreate(
            name="Legacy Effects Policy",
            description="Old format",
            effects="{'economic_health': 3, 'avg_happiness': 1}",
        ))
        session.close()

        client = _make_client()
        r = client.get("/queries/policies")
        assert r.status_code == 200
        policies = r.json()

        legacy = next((p for p in policies if p["name"] == "Legacy Effects Policy"), None)
        assert legacy is not None
        # effects_parsed should gracefully parse the Python repr
        assert isinstance(legacy.get("effects_parsed"), dict)


class TestHistoricalAnalyticsEndpoint:
    """Verify /queries/analytics/historical and /queries/backups endpoints."""

    def test_backups_endpoint_returns_list(self):
        """GET /queries/backups should return a list (possibly empty)."""
        _seed_citizen()
        client = _make_client()
        r = client.get("/queries/backups")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_historical_analytics_endpoint_returns_list(self):
        """GET /queries/analytics/historical should return a list."""
        _seed_citizen(n=3)
        client = _make_client()
        r = client.get("/queries/analytics/historical")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_analytics_endpoint_has_simulation_day(self):
        """GET /queries/analytics snapshots should include simulation_day field."""
        from autosociety.backend.core.metrics import record_snapshot
        record_snapshot(tick=1, simulation_day=1, gdp=500.0,
                        crime_rate=0.05, tax_revenue=75.0, active_businesses=0)

        _seed_citizen()
        client = _make_client()
        r = client.get("/queries/analytics")
        assert r.status_code == 200
        data = r.json()
        assert "snapshots" in data
        snapshots = data["snapshots"]
        assert len(snapshots) >= 1
        for snap in snapshots:
            assert "simulation_day" in snap, "simulation_day field missing from analytics response"
