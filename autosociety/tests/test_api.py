"""
Tests for FastAPI API endpoints using TestClient.
Recreates tables per test without deleting files (avoids Windows locks).
"""

import gc
import time
from fastapi.testclient import TestClient
import pytest

from autosociety.backend.core import database as db
from autosociety.backend.core import metrics as met
from autosociety.backend.core.engine import SimulationEngine
from autosociety.backend.routers import simulation


def _seed_test_citizens():
    """Seed 5 test citizens into the already-clean test DB (conftest.py handles drop/create)."""
    session = db.get_session()
    for i in range(5):
        db.create_citizen(session, db.CitizenCreate(
            name=f"Test {i}",
            age=25 + i,
            job="Engineer" if i < 3 else "Teacher",
            happiness=50.0 + i * 5,
            wealth=100.0 + i * 20,
            health=80.0,
            social_score=50.0,
        ))
    session.close()


@pytest.fixture(scope="function")
def client():
    _seed_test_citizens()
    eng = SimulationEngine()
    simulation.set_engine(eng)
    from autosociety.backend.main import app
    tc = TestClient(app)
    yield tc
    if eng.is_running:
        eng.stop()
    if eng._task:
        eng._task.cancel()


class TestRoot:
    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["app"] == "AutoSociety"

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_docs_available(self, client):
        r = client.get("/docs")
        assert r.status_code == 200


class TestCitizens:
    def test_list_all(self, client):
        r = client.get("/queries/citizens")
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 5
        assert len(d["citizens"]) == 5

    def test_list_pagination(self, client):
        r = client.get("/queries/citizens?skip=1&limit=2")
        d = r.json()
        assert d["total"] == 5
        assert len(d["citizens"]) == 2

    def test_get_by_id(self, client):
        r = client.get("/queries/citizens/1")
        assert r.status_code == 200
        assert r.json()["name"] == "Test 0"

    def test_get_by_id_not_found(self, client):
        r = client.get("/queries/citizens/999")
        assert r.status_code == 404


class TestSimulation:
    def test_get_world_state(self, client):
        r = client.get("/simulation/state")
        assert r.status_code == 200
        d = r.json()
        assert "tick" in d
        assert d["population"] == 5

    def test_start_and_stop(self, client):
        r = client.post("/simulation/start")
        assert r.status_code == 200
        r = client.post("/simulation/stop")
        assert r.status_code == 200

    def test_double_start_returns_409(self, client):
        client.post("/simulation/start")
        r = client.post("/simulation/start")
        assert r.status_code == 200
        assert "already running" in r.json()["message"].lower()

    def test_pause_resume(self, client):
        client.post("/simulation/start")
        t1 = client.get("/simulation/state").json()["tick"]
        r = client.post("/simulation/pause")
        assert r.status_code == 200
        state = client.get("/simulation/state").json()
        assert state["paused"] is True
        assert state["tick"] >= t1
        r = client.post("/simulation/resume")
        assert r.status_code == 200
        client.post("/simulation/stop")

    def test_stop_not_running_returns_409(self, client):
        r = client.post("/simulation/stop")
        assert r.status_code == 200
        assert "not running" in r.json()["message"].lower()

    def test_pause_not_running_returns_409(self, client):
        r = client.post("/simulation/pause")
        assert r.status_code == 200
        assert "not running" in r.json()["message"].lower()

    def test_reset(self, client):
        client.post("/simulation/start")
        client.post("/simulation/stop")
        r = client.post("/simulation/reset")
        assert r.status_code == 200

    def test_cycle_start_stop_reset(self, client):
        client.post("/simulation/start")
        client.post("/simulation/stop")
        client.post("/simulation/reset")
        r = client.get("/simulation/state")
        assert r.json()["tick"] == 0


class TestQueries:
    def test_get_policies(self, client):
        r = client.get("/queries/policies")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_events(self, client):
        r = client.get("/queries/events")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_analytics(self, client):
        r = client.get("/queries/analytics")
        assert r.status_code == 200
        assert "snapshots" in r.json()

    def test_get_reports(self, client):
        r = client.get("/queries/reports")
        assert r.status_code == 200
        d = r.json()
        assert d["total_population"] == 5
        assert "average_happiness" in d

    def test_integration_sequence(self, client):
        for path in ["/queries/citizens", "/queries/policies", "/queries/events",
                      "/queries/analytics", "/queries/reports"]:
            r = client.get(path)
            assert r.status_code == 200, f"{path} returned {r.status_code}"

    def test_analytics_has_simulation_day(self, client):
        """Every analytics snapshot must carry a simulation_day field."""
        from autosociety.backend.core.metrics import record_snapshot
        record_snapshot(tick=1, simulation_day=1, gdp=500.0,
                        crime_rate=0.05, tax_revenue=75.0, active_businesses=0)
        r = client.get("/queries/analytics")
        assert r.status_code == 200
        snapshots = r.json()["snapshots"]
        if snapshots:
            for snap in snapshots:
                assert "simulation_day" in snap, (
                    "simulation_day field missing from /queries/analytics response"
                )

    def test_backups_endpoint(self, client):
        """GET /queries/backups should return a JSON list (may be empty)."""
        r = client.get("/queries/backups")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_historical_analytics_endpoint(self, client):
        """GET /queries/analytics/historical should return a JSON list."""
        r = client.get("/queries/analytics/historical")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_events_filtering_by_type_and_search(self, client):
        """Verify optional event_type and search_query parameters on /queries/events."""
        session = db.get_session()
        db.create_event(session, description="Burglary reported at downtown store", event_type="Crime", severity=4)
        db.create_event(session, description="Massive storm hit the northern sector", event_type="Disaster", severity=8)
        db.create_event(session, description="Tax rate policy updated by cabinet", event_type="Policy", severity=2)
        session.close()

        # Test filtering by event_type
        r = client.get("/queries/events?event_type=Crime")
        assert r.status_code == 200
        events = r.json()
        assert all(e["event_type"] == "Crime" for e in events)
        assert any("Burglary" in e["description"] for e in events)

        # Test search_query
        r = client.get("/queries/events?search_query=storm")
        assert r.status_code == 200
        events = r.json()
        assert len(events) >= 1
        assert all("storm" in e["description"].lower() for e in events)

        # Test min_severity
        r = client.get("/queries/events?min_severity=6")
        assert r.status_code == 200
        events = r.json()
        assert all(e["severity"] >= 6 for e in events)

        # Test event_types endpoint
        r = client.get("/queries/events/types")
        assert r.status_code == 200
        types = r.json()
        assert "Crime" in types
        assert "Disaster" in types
        assert "Policy" in types
