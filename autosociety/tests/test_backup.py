"""
Tests for the database backup and historical restoration utilities.

Verifies:
  a) create_backup() produces a valid file with correct citizen data
  b) VACUUM INTO works while DB is open (no Windows file-lock error)
  c) list_backups() enumerates backup files correctly
  d) load_historical_snapshots() reads tick data from a backup
  e) merge_all_historical_snapshots() combines multiple backup runs
"""

import sqlite3
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from autosociety.backend.core.database import (
    get_session, create_citizen, CitizenCreate, DB_PATH, DATA_DIR, init_db,
)
from autosociety.backend.core.metrics import record_snapshot, init_metrics_db


def _seed_citizens(n=3):
    """Seed n test citizens into the test database."""
    session = get_session()
    for i in range(n):
        create_citizen(session, CitizenCreate(
            name=f"Backup Test Citizen {i}",
            age=25 + i,
            job="Engineer",
            happiness=60.0 + i,
            wealth=200.0 + i * 10,
            health=80.0,
            social_score=50.0,
        ))
    session.close()


class TestCreateBackup:
    """Test backup file creation using VACUUM INTO."""

    def test_create_backup_produces_file(self, tmp_path):
        """create_backup() should produce a non-empty .db file."""
        from autosociety.backend.core import backup as bk_module

        # Redirect BACKUPS_DIR to a temp directory for this test
        with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
            backup_path = bk_module.create_backup()

        assert backup_path.exists(), "Backup file should exist"
        assert backup_path.stat().st_size > 0, "Backup file should not be empty"
        assert backup_path.suffix == ".db", "Backup should have .db extension"

    def test_create_backup_with_label(self, tmp_path):
        """A label parameter should appear in the backup filename."""
        from autosociety.backend.core import backup as bk_module

        with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
            backup_path = bk_module.create_backup(label="test_label")

        assert "test_label" in backup_path.name

    def test_backup_preserves_citizen_data(self, tmp_path):
        """Citizen rows in the backup should match the source database."""
        _seed_citizens(3)

        from autosociety.backend.core import backup as bk_module
        with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
            backup_path = bk_module.create_backup()

        # Read citizens from the backup directly via sqlite3
        conn = sqlite3.connect(str(backup_path))
        rows = conn.execute("SELECT name FROM citizens ORDER BY id").fetchall()
        conn.close()

        assert len(rows) == 3, f"Expected 3 citizens in backup, got {len(rows)}"

    def test_backup_works_while_db_is_open(self, tmp_path):
        """
        VACUUM INTO must succeed even while other connections hold WAL locks.
        Simulates Windows environment by holding an open connection.
        """
        # Keep an open connection to simulate a live FastAPI connection pool
        open_conn = sqlite3.connect(str(DB_PATH))
        open_conn.execute("SELECT 1")

        from autosociety.backend.core import backup as bk_module
        try:
            with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
                backup_path = bk_module.create_backup()
            assert backup_path.exists()
        finally:
            open_conn.close()

    def test_backup_creates_backups_dir(self, tmp_path):
        """create_backup() should create the backups directory if it doesn't exist."""
        new_backups_dir = tmp_path / "nested" / "backups"
        assert not new_backups_dir.exists()

        from autosociety.backend.core import backup as bk_module
        with patch.object(bk_module, "BACKUPS_DIR", new_backups_dir):
            bk_module.create_backup()

        assert new_backups_dir.exists()


class TestListBackups:
    """Test backup enumeration."""

    def test_list_backups_empty_dir(self, tmp_path):
        """list_backups() returns empty list when no backups exist."""
        from autosociety.backend.core import backup as bk_module
        with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
            result = bk_module.list_backups()
        assert result == []

    def test_list_backups_finds_files(self, tmp_path):
        """list_backups() finds backup files and returns their metadata."""
        from autosociety.backend.core import backup as bk_module

        # Create two backups
        with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
            p1 = bk_module.create_backup(label="first")
            p2 = bk_module.create_backup(label="second")
            result = bk_module.list_backups()

        assert len(result) == 2
        filenames = [r["filename"] for r in result]
        assert p1.name in filenames
        assert p2.name in filenames

    def test_list_backups_metadata_fields(self, tmp_path):
        """Each backup dict has filename, path, size_kb, created_at."""
        from autosociety.backend.core import backup as bk_module
        with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
            bk_module.create_backup()
            result = bk_module.list_backups()

        assert len(result) == 1
        entry = result[0]
        for field in ("filename", "path", "size_kb", "created_at"):
            assert field in entry, f"Missing field '{field}' in backup metadata"
        assert entry["size_kb"] > 0


class TestLoadHistoricalSnapshots:
    """Test reading tick_snapshots from backup files."""

    def test_load_snapshots_from_backup(self, tmp_path):
        """Snapshots written to live DB should be readable from a backup."""
        # Record some snapshots in the test metrics DB
        for t in range(1, 4):
            record_snapshot(tick=t, simulation_day=t, gdp=100.0 * t,
                            crime_rate=0.01, tax_revenue=10.0, active_businesses=0)

        from autosociety.backend.core import backup as bk_module
        with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
            # Backup the main DB (it won't have metrics, but tests the shape)
            backup_path = bk_module.create_backup()

        # The test autosociety.db won't contain tick_snapshots (that's metrics.db).
        # For this test, create a synthetic backup with snapshots using sqlite3.
        synthetic = tmp_path / "autosociety_20260101_120000_synthetic.db"
        conn = sqlite3.connect(str(synthetic))
        conn.execute("""
            CREATE TABLE tick_snapshots (
                id INTEGER PRIMARY KEY,
                tick INTEGER,
                simulation_day INTEGER,
                population INTEGER,
                avg_happiness REAL,
                avg_wealth REAL,
                avg_health REAL,
                employment_rate REAL,
                gdp REAL,
                crime_rate REAL,
                tax_revenue REAL,
                active_businesses INTEGER,
                political_stability REAL,
                economic_health REAL,
                recorded_at TEXT
            )
        """)
        for t in range(1, 4):
            conn.execute(
                "INSERT INTO tick_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (t, t, t, 30, 55.0, 300.0, 75.0, 0.9, 1500.0, 0.02, 200.0, 0, 50.0, 50.0, "2026-01-01"),
            )
        conn.commit()
        conn.close()

        with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
            snapshots = bk_module.load_historical_snapshots(synthetic)

        assert len(snapshots) == 3
        for i, snap in enumerate(snapshots):
            assert snap["tick"] == i + 1
            assert snap["simulation_day"] == i + 1
            assert "run_label" in snap

    def test_load_snapshots_missing_table(self, tmp_path):
        """load_historical_snapshots returns empty list for DBs without the table."""
        from autosociety.backend.core import backup as bk_module
        empty_db = tmp_path / "autosociety_20260101_000000_empty.db"
        conn = sqlite3.connect(str(empty_db))
        conn.close()

        with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
            snapshots = bk_module.load_historical_snapshots(empty_db)
        assert snapshots == []

    def test_load_snapshots_run_label_from_filename(self, tmp_path):
        """run_label is derived from the backup filename timestamp."""
        from autosociety.backend.core import backup as bk_module
        db_path = tmp_path / "autosociety_20260716_093045.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE tick_snapshots "
            "(id INTEGER PRIMARY KEY, tick INTEGER, simulation_day INTEGER, "
            "population INTEGER, avg_happiness REAL, avg_wealth REAL, avg_health REAL, "
            "employment_rate REAL, gdp REAL, crime_rate REAL, tax_revenue REAL, "
            "active_businesses INTEGER, political_stability REAL, economic_health REAL, "
            "recorded_at TEXT)"
        )
        conn.execute(
            "INSERT INTO tick_snapshots VALUES (1,1,1,30,50.0,200.0,75.0,0.9,1000.0,0.01,150.0,0,50.0,50.0,'2026')"
        )
        conn.commit()
        conn.close()

        with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
            snapshots = bk_module.load_historical_snapshots(db_path)

        assert len(snapshots) == 1
        assert "Run 2026-07-16" in snapshots[0]["run_label"]


class TestMergeHistoricalSnapshots:
    """Test merging multiple backup runs into unified timeline."""

    def test_merge_empty_backups_dir(self, tmp_path):
        """merge_all_historical_snapshots returns empty list when no backups exist."""
        from autosociety.backend.core import backup as bk_module
        with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
            result = bk_module.merge_all_historical_snapshots()
        assert result == []

    def test_merge_two_runs(self, tmp_path):
        """Merging two backup files returns combined and sorted snapshots."""
        from autosociety.backend.core import backup as bk_module

        def _make_backup_db(path: Path, ticks: list):
            conn = sqlite3.connect(str(path))
            conn.execute(
                "CREATE TABLE tick_snapshots "
                "(id INTEGER PRIMARY KEY, tick INTEGER, simulation_day INTEGER, "
                "population INTEGER, avg_happiness REAL, avg_wealth REAL, avg_health REAL, "
                "employment_rate REAL, gdp REAL, crime_rate REAL, tax_revenue REAL, "
                "active_businesses INTEGER, political_stability REAL, economic_health REAL, "
                "recorded_at TEXT)"
            )
            for t in ticks:
                conn.execute(
                    "INSERT INTO tick_snapshots VALUES (?,?,?,30,50.0,200.0,75.0,0.9,1000.0,0.01,150.0,0,50.0,50.0,'2026')",
                    (t, t, t),
                )
            conn.commit()
            conn.close()

        p1 = tmp_path / "autosociety_20260101_080000.db"
        p2 = tmp_path / "autosociety_20260102_080000.db"
        _make_backup_db(p1, [1, 2, 3])
        _make_backup_db(p2, [1, 2])

        with patch.object(bk_module, "BACKUPS_DIR", tmp_path):
            result = bk_module.merge_all_historical_snapshots()

        assert len(result) == 5  # 3 from run1 + 2 from run2
        # All rows should have a run_label
        assert all("run_label" in r for r in result)
