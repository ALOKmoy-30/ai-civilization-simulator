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
