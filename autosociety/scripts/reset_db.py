#!/usr/bin/env python3
"""
Drop and recreate all DB tables without deleting the file.

SAFETY: A timestamped .bak copy is made of both databases before any
tables are dropped. If you run this by mistake you can restore with:
    copy data_storage\autosociety_20260716_010340.bak data_storage\autosociety.db
"""

import shutil
from datetime import datetime
from autosociety.backend.core import database as db
from autosociety.backend.core import metrics as met


def _backup(path):
    """Copy a SQLite file to a timestamped .bak file in the same directory."""
    if path.exists() and path.stat().st_size > 0:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = path.with_name(f"{path.stem}_{ts}.bak")
        shutil.copy2(path, backup)
        print(f"  Backed up → {backup.name}")


def reset():
    print("Creating safety backups...")
    _backup(db.DB_PATH)
    _backup(met.METRICS_DB_PATH)

    print("Dropping all tables...")
    db.Base.metadata.drop_all(bind=db.engine)
    met.MetricsBase.metadata.drop_all(bind=met.metrics_engine)

    print("Recreating all tables...")
    db.Base.metadata.create_all(bind=db.engine)
    met.MetricsBase.metadata.create_all(bind=met.metrics_engine)

    print("Database reset complete.")


if __name__ == "__main__":
    reset()
