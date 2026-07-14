"""
Tests for FastAPI API endpoints using TestClient.
Reuses a single test DB file, recreating tables per test without deleting.
"""

import gc
import time
import random
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from autosociety.backend.core import database as db
from autosociety.backend.core import metrics as met
from autosociety.backend.core.engine import SimulationEngine
from autosociety.backend.routers import simulation

TEST_DB = db.DATA_DIR / "test_api.db"
TEST_METRICS = db.DATA_DIR / "test_metrics_api.db"


def _reset_db():
    """Drop and recreate all tables, seed 5 citizens."""
    db.engine.dispose()
    met.metrics_engine.dispose()
    gc.collect()
    time.sleep(0.05)

    # Save originals to restore later
    _reset_db._orig_engine = db.engine
    _reset_db._orig_session = db.SessionLocal
    _reset_db._orig_metrics_engine = met.metrics_engine
    _reset_db._orig_metrics_session = met.MetricsSession

    # Re-engines from same files
    db.engine = db.create_engine(
        f"sqlite:///{TEST_DB}", connect_args={"check_same_thread": False}
    )
    db.SessionLocal = db.sessionmaker(autocommit=False, autoflush=False, bind=db.engine)

    met.metrics_engine = met.create_engine(
        f"sqlite:///{TEST_METRICS}", connect_args={"check_same_thread": False}
    )
    met.MetricsSession = met.sessionmaker(autocommit=False, autoflush=False, bind=met.metrics_engine)

    # Fresh tables
    db.Base.metadata.drop_all(bind=db.engine)
    db.Base.metadata.create_all(bind=db.engine)
    met.MetricsBase.metadata.create_all(bind=met.metrics_engine)

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


def _restore_db():
    """Restore original engine/session after test."""
    if hasattr(_reset_db, '_orig_engine'):
        db.engine = _reset_db._orig_engine
        db.SessionLocal = _reset_db._orig_session
        met.metrics_engine = _reset_db._orig_metrics_engine
        met.MetricsSession = _reset_db._orig_metrics_session


@pytest.fixture(scope="function")
def client():
    _reset_db()

    eng = SimulationEngine()
    simulation.set_engine(eng)

    from autosociety.backend.main import app
    tc = TestClient(app)

    yield tc

    if eng.is_running:
        eng.stop()
    if eng._task:
        eng._task.cancel()
        try:
            import asyncio
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))
        except Exception:
            pass
    _restore_db()


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
        assert r.json()["status"] == "ok"
        r = client.post("/simulation/stop")
        assert r.status_code == 200

    def test_double_start_returns_409(self, client):
        client.post("/simulation/start")
        r = client.post("/simulation/start")
        assert r.status_code == 409
        client.post("/simulation/stop")

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
        assert r.status_code == 409

    def test_pause_not_running_returns_409(self, client):
        r = client.post("/simulation/pause")
        assert r.status_code == 409

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
