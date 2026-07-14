#!/usr/bin/env python3
"""Drop and recreate all DB tables without deleting the file."""

from autosociety.backend.core import database as db
from autosociety.backend.core import metrics as met


def reset():
    print("Dropping all tables...")
    db.Base.metadata.drop_all(bind=db.engine)
    met.MetricsBase.metadata.drop_all(bind=met.metrics_engine)
    print("Recreating all tables...")
    db.Base.metadata.create_all(bind=db.engine)
    met.MetricsBase.metadata.create_all(bind=met.metrics_engine)
    print("Database reset complete.")


if __name__ == "__main__":
    reset()
