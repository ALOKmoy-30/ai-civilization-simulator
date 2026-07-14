"""
Append-only historical metrics logger.
Writes one snapshot per tick; never overwrites prior history.
"""

import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from sqlalchemy import Column, Integer, Float, DateTime, create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm import declarative_base

from autosociety.backend.core.database import DATA_DIR, get_session, list_citizens, count_citizens
from autosociety.backend.core.config import world_config as cfg
from autosociety.backend.core.database import get_or_create_world_state

# ── Metrics SQLite Table (separate from main DB to enable easy CSV export) ──

METRICS_DB_PATH = DATA_DIR / "metrics.db"
METRICS_URL = f"sqlite:///{METRICS_DB_PATH}"
metrics_engine = create_engine(METRICS_URL, connect_args={"check_same_thread": False})
MetricsSession = sessionmaker(autocommit=False, autoflush=False, bind=metrics_engine)
MetricsBase = declarative_base()


class TickSnapshot(MetricsBase):
    """One row per tick: append-only historical metric."""

    __tablename__ = "tick_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tick = Column(Integer, index=True)
    population = Column(Integer)
    avg_happiness = Column(Float)
    avg_wealth = Column(Float)
    avg_health = Column(Float)
    employment_rate = Column(Float)
    gdp = Column(Float)  # total wages + business revenue this tick
    crime_rate = Column(Float)
    tax_revenue = Column(Float)
    active_businesses = Column(Integer)
    political_stability = Column(Float)
    economic_health = Column(Float)
    recorded_at = Column(DateTime, default=datetime.utcnow)


def init_metrics_db():
    """Create the metrics table if it doesn't exist."""
    MetricsBase.metadata.create_all(bind=metrics_engine)


def record_snapshot(tick: int, gdp: float, crime_rate: float,
                    tax_revenue: float, active_businesses: int,
                    extra: Optional[Dict[str, float]] = None) -> TickSnapshot:
    """
    Record a single tick's snapshot. Appends a row — never modifies history.
    """
    session = get_session()
    citizens = list_citizens(session)
    world = get_or_create_world_state(session)

    num_citizens = len(citizens)
    avg_happiness = sum(c.happiness for c in citizens) / num_citizens if num_citizens else 0
    avg_wealth = sum(c.wealth for c in citizens) / num_citizens if num_citizens else 0
    avg_health = sum(c.health for c in citizens) / num_citizens if num_citizens else 0

    # Employment rate: citizens with a job (non-empty job field)
    employed = sum(1 for c in citizens if c.job)
    employment_rate = employed / num_citizens if num_citizens else 0

    session.close()

    m_session = MetricsSession()
    snapshot = TickSnapshot(
        tick=tick,
        population=num_citizens,
        avg_happiness=round(avg_happiness, 2),
        avg_wealth=round(avg_wealth, 2),
        avg_health=round(avg_health, 2),
        employment_rate=round(employment_rate, 4),
        gdp=round(gdp, 2),
        crime_rate=round(crime_rate, 4),
        tax_revenue=round(tax_revenue, 2),
        active_businesses=active_businesses,
        political_stability=round(world.political_stability, 2) if world else 50.0,
        economic_health=round(world.economic_health, 2) if world else 50.0,
    )
    m_session.add(snapshot)
    m_session.commit()
    m_session.close()

    return snapshot


def get_all_snapshots() -> List[TickSnapshot]:
    """Return all recorded snapshots in tick order."""
    m_session = MetricsSession()
    snapshots = m_session.query(TickSnapshot).order_by(TickSnapshot.tick).all()
    m_session.close()
    return snapshots


def export_metrics_csv() -> str:
    """
    Export all metrics as a CSV string.
    Students can save this to a file and chart in Excel or Plotly.
    """
    snapshots = get_all_snapshots()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "tick", "population", "avg_happiness", "avg_wealth", "avg_health",
        "employment_rate", "gdp", "crime_rate", "tax_revenue",
        "active_businesses", "political_stability", "economic_health",
    ])
    for s in snapshots:
        writer.writerow([
            s.tick, s.population, s.avg_happiness, s.avg_wealth, s.avg_health,
            s.employment_rate, s.gdp, s.crime_rate, s.tax_revenue,
            s.active_businesses, s.political_stability, s.economic_health,
        ])
    return output.getvalue()


def export_metrics_csv_to_file(path: Optional[Path] = None) -> Path:
    """Write metrics CSV to disk. Default path: data_storage/metrics.csv."""
    if path is None:
        path = DATA_DIR / "metrics.csv"
    csv_content = export_metrics_csv()
    path.write_text(csv_content)
    return path
