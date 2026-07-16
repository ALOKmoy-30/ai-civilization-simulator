"""
Database backup and historical analytics restoration utilities.

Key design decisions:
- Uses SQLite's VACUUM INTO for backups — this is WAL-safe and works even
  when the database file is open by FastAPI/SQLAlchemy on Windows.
- Backups are stored in data_storage/backups/ to keep them separate from
  the live .db files and .bak files in data_storage/.
- Historical snapshots from backup files are returned as plain dicts (not
  ORM objects) so they can be merged and served over the API without
  binding a second SQLAlchemy engine permanently.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from autosociety.backend.core.database import DATA_DIR, DB_PATH
from autosociety.backend.core.metrics import METRICS_DB_PATH

logger = logging.getLogger(__name__)

# Backups directory — created on first use
BACKUPS_DIR = DATA_DIR / "backups"


def create_backup(label: Optional[str] = None) -> Path:
    """
    Create a timestamped backup of the live autosociety.db and metrics.db using VACUUM INTO.

    VACUUM INTO is WAL-safe: it can run while the database is open and being
    written to by other connections, making it Windows file-lock safe.

    Args:
        label: Optional descriptive suffix for the backup filename.

    Returns:
        Path to the newly created main backup file.
    """
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{label}" if label else ""
    backup_path = BACKUPS_DIR / f"autosociety_{ts}{suffix}.db"
    metrics_backup_path = BACKUPS_DIR / f"metrics_{ts}{suffix}.db"

    if backup_path.exists():
        try:
            backup_path.unlink()
        except OSError:
            pass
    if metrics_backup_path.exists():
        try:
            metrics_backup_path.unlink()
        except OSError:
            pass

    # Use VACUUM INTO — the only SQLite mechanism guaranteed to work
    # while other connections hold WAL-mode read/write locks.
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(f"VACUUM INTO '{backup_path}'")
        conn.commit()
    finally:
        conn.close()

    # Also backup metrics.db where the tick_snapshots table resides
    if METRICS_DB_PATH.exists():
        conn_m = sqlite3.connect(str(METRICS_DB_PATH))
        try:
            conn_m.execute(f"VACUUM INTO '{metrics_backup_path}'")
            conn_m.commit()
        except Exception as e:
            logger.warning("Failed to backup metrics DB: %s", e)
        finally:
            conn_m.close()

    logger.info("Backup created: %s (%.1f KB)", backup_path.name,
                backup_path.stat().st_size / 1024)
    return backup_path


def list_backups() -> List[Dict[str, Any]]:
    """
    Return metadata for all backup files in data_storage/backups/.

    Returns a list of dicts with keys:
        - filename: str
        - path: str (absolute)
        - size_kb: float
        - created_at: str (ISO-format from filename timestamp)
    """
    if not BACKUPS_DIR.exists():
        return []

    results = []
    for p in sorted(BACKUPS_DIR.glob("autosociety_*.db")):
        # Parse timestamp from filename: autosociety_YYYYMMDD_HHMMSS[_label].db
        parts = p.stem.split("_")
        try:
            dt = datetime.strptime(f"{parts[1]}_{parts[2]}", "%Y%m%d_%H%M%S")
            created_at = dt.isoformat()
        except (IndexError, ValueError):
            created_at = "unknown"

        results.append({
            "filename": p.name,
            "path": str(p),
            "size_kb": round(p.stat().st_size / 1024, 1),
            "created_at": created_at,
        })
    return results


def load_historical_snapshots(backup_path: Path) -> List[Dict[str, Any]]:
    """
    Read all tick_snapshots rows from a backup database file (or its metrics companion).

    Returns a list of dicts. Each dict includes a ``run_label`` field
    derived from the backup filename timestamp so charts can distinguish runs.

    Args:
        backup_path: Path to a backup .db file.

    Returns:
        List of snapshot dicts, or empty list if the file lacks the table.
    """
    if not backup_path.exists():
        return []

    # Derive a human-readable run label from the filename
    parts = backup_path.stem.split("_")
    try:
        dt = datetime.strptime(f"{parts[1]}_{parts[2]}", "%Y%m%d_%H%M%S")
        run_label = dt.strftime("Run %Y-%m-%d %H:%M")
    except (IndexError, ValueError):
        run_label = backup_path.stem

    # If this is an autosociety_*.db file, check if it directly contains tick_snapshots.
    # If not, check if the corresponding metrics_*.db file exists alongside it.
    target_path = backup_path
    if backup_path.name.startswith("autosociety_"):
        metrics_companion = backup_path.parent / backup_path.name.replace("autosociety_", "metrics_", 1)
        if metrics_companion.exists():
            target_path = metrics_companion

    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(
                "SELECT * FROM tick_snapshots ORDER BY tick ASC"
            ).fetchall()
        except sqlite3.OperationalError:
            # Table doesn't exist in this backup
            return []

        snapshots = []
        for row in rows:
            d = dict(row)
            d["run_label"] = run_label
            # Back-fill simulation_day if column was absent in old schema
            if d.get("simulation_day") is None:
                d["simulation_day"] = d.get("tick", 0)
            snapshots.append(d)
        return snapshots
    finally:
        conn.close()


def merge_all_historical_snapshots() -> List[Dict[str, Any]]:
    """
    Load and merge tick_snapshots from every backup file.

    Returns all rows from all backup runs, sorted by (run_label, tick).
    Each row carries a ``run_label`` field for chart legend display.
    """
    if not BACKUPS_DIR.exists():
        return []

    all_snapshots: List[Dict[str, Any]] = []
    seen_paths = set()
    for p in sorted(BACKUPS_DIR.glob("autosociety_*.db")):
        snapshots = load_historical_snapshots(p)
        all_snapshots.extend(snapshots)
        seen_paths.add(p)
        if p.name.startswith("autosociety_"):
            seen_paths.add(p.parent / p.name.replace("autosociety_", "metrics_", 1))

    for p in sorted(BACKUPS_DIR.glob("metrics_*.db")):
        if p not in seen_paths:
            all_snapshots.extend(load_historical_snapshots(p))

    all_snapshots.sort(key=lambda s: (s.get("run_label", ""), s.get("tick", 0)))
    return all_snapshots
