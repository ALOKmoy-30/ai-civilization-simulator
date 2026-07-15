"""
conftest.py — pytest session fixtures for AutoSociety tests.

KEY GUARANTEE: Tests NEVER touch the live simulation databases
(autosociety.db / metrics.db). Instead they operate against
test_autosociety.db and test_metrics.db inside data_storage/.

How it works:
  - database.py and metrics.py already check PYTEST_CURRENT_TEST (set
    automatically by pytest before any module is imported) and redirect
    their engines to the test-only DB paths.
  - The `isolated_db` autouse fixture (scope="function") drops and
    recreates all test-DB tables around every single test, so each test
    starts with a completely clean slate.
"""

import os
import pytest

# Ensure TESTING env var is set for any process that doesn't get
# PYTEST_CURRENT_TEST (e.g. subprocess spawned inside a test).
os.environ.setdefault("TESTING", "1")


@pytest.fixture(autouse=True, scope="function")
def isolated_db():
    """
    Drop-and-recreate all tables in the TEST databases before every test.

    Because database.py / metrics.py already redirect their engines to
    test_autosociety.db / test_metrics.db when PYTEST_CURRENT_TEST is set,
    these drop_all calls are 100% safe and never touch the live data.
    """
    # Import here so the environment variable check in database.py / metrics.py
    # has already run by the time we import these engines.
    from autosociety.backend.core.database import Base, engine, init_db
    from autosociety.backend.core.metrics import MetricsBase, metrics_engine, init_metrics_db

    # Tear down & rebuild test tables before each test
    Base.metadata.drop_all(bind=engine)
    MetricsBase.metadata.drop_all(bind=metrics_engine)
    init_db()
    init_metrics_db()

    yield  # test runs here

    # Clean up after test (optional but keeps test DB small)
    Base.metadata.drop_all(bind=engine)
    MetricsBase.metadata.drop_all(bind=metrics_engine)
