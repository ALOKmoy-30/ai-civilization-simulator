"""Query endpoints — read-only access to simulation data."""

import json
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime

from autosociety.backend.core.database import (
    get_session, get_citizen, list_citizens, get_citizen_by_name,
    count_citizens, get_or_create_world_state,
)
from autosociety.backend.core.metrics import get_all_snapshots

router = APIRouter(prefix="/queries", tags=["queries"])


# ── Pydantic models ─────────────────────────────────────────────────

class CitizenResponse(BaseModel):
    id: int
    name: str
    age: int
    job: str
    happiness: float
    wealth: float
    health: float
    social_score: float
    created_at: datetime
    updated_at: datetime


class CitizenListResponse(BaseModel):
    total: int
    citizens: List[CitizenResponse]


class PolicyResponse(BaseModel):
    id: int
    name: str
    description: str
    effects: str                        # raw JSON string of numeric adjustments
    effects_parsed: Dict[str, Any]      # deserialized for the frontend
    reasoning_summary: Optional[str]    # full Governor reasoning / ORDER text
    enacted_day: Optional[int]          # simulation_day when enacted
    decision_status: Optional[str]      # approved / rejected / modified
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EventResponse(BaseModel):
    id: int
    description: str
    event_type: str
    severity: int
    created_at: datetime
    affected_citizens: Optional[str] = None


class AnalyticsResponse(BaseModel):
    tick: int
    simulation_day: int
    population: int
    avg_happiness: float
    avg_wealth: float
    gdp: float
    crime_rate: float
    employment_rate: float
    tax_revenue: float
    active_businesses: int
    political_stability: float
    economic_health: float


class AnalyticsListResponse(BaseModel):
    snapshots: List[AnalyticsResponse]


class BackupInfo(BaseModel):
    filename: str
    path: str
    size_kb: float
    created_at: str


class HistoricalSnapshotResponse(BaseModel):
    tick: int
    simulation_day: int
    run_label: str
    population: int
    avg_happiness: Optional[float] = None
    avg_wealth: Optional[float] = None
    gdp: Optional[float] = None
    crime_rate: Optional[float] = None
    employment_rate: Optional[float] = None
    tax_revenue: Optional[float] = None
    active_businesses: Optional[int] = None
    political_stability: Optional[float] = None
    economic_health: Optional[float] = None


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/citizens", response_model=CitizenListResponse)
async def get_citizens(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    """List all citizens with pagination."""
    session = get_session()
    citizens = list_citizens(session, skip=skip, limit=limit)
    total = count_citizens(session)
    session.close()
    return CitizenListResponse(
        total=total,
        citizens=[
            CitizenResponse(
                id=c.id, name=c.name, age=c.age, job=c.job,
                happiness=c.happiness, wealth=c.wealth, health=c.health,
                social_score=c.social_score,
                created_at=c.created_at, updated_at=c.updated_at,
            )
            for c in citizens
        ],
    )


@router.get("/citizens/{citizen_id}", response_model=CitizenResponse)
async def get_citizen_by_id(citizen_id: int):
    """Get a single citizen by ID."""
    session = get_session()
    citizen = get_citizen(session, citizen_id)
    session.close()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")
    return CitizenResponse(
        id=citizen.id, name=citizen.name, age=int(citizen.age), job=citizen.job,
        happiness=citizen.happiness, wealth=citizen.wealth, health=citizen.health,
        social_score=citizen.social_score,
        created_at=citizen.created_at, updated_at=citizen.updated_at,
    )


def _parse_policy_effects(effects_str: str) -> Dict[str, Any]:
    """Parse the effects field into a dict. Handles both JSON and legacy Python repr."""
    if not effects_str:
        return {}
    try:
        return json.loads(effects_str)
    except (json.JSONDecodeError, TypeError):
        pass
    # Legacy fallback: try to eval simple Python dicts (e.g. "{'key': 1}")
    try:
        import ast
        result = ast.literal_eval(effects_str)
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    return {}


@router.get("/policies", response_model=List[PolicyResponse])
async def get_policies():
    """List all enacted policies with full detail."""
    from autosociety.backend.core.database import list_policies
    session = get_session()
    policies = list_policies(session)
    session.close()
    return [
        PolicyResponse(
            id=p.id,
            name=p.name,
            description=p.description or "",
            effects=p.effects or "{}",
            effects_parsed=_parse_policy_effects(p.effects or "{}"),
            reasoning_summary=getattr(p, "reasoning_summary", None),
            enacted_day=getattr(p, "enacted_day", None),
            decision_status=getattr(p, "decision_status", "approved"),
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in policies
    ]


@router.get("/events", response_model=List[EventResponse])
async def get_events(
    limit: int = Query(50, ge=1, le=500),
    event_type: Optional[str] = Query(None, description="Filter by exact event_type (e.g. citizen_action, disaster)"),
    search_query: Optional[str] = Query(None, description="Search keyword within event descriptions (case-insensitive)"),
    min_severity: Optional[int] = Query(None, ge=1, le=10, description="Minimum severity level to include"),
):
    """List recent events with optional server-side filtering."""
    from autosociety.backend.core.database import Event, SessionLocal
    session = SessionLocal()

    query = session.query(Event)

    # Apply filters dynamically
    if event_type and event_type.lower() != "all":
        query = query.filter(Event.event_type.ilike(event_type))
    if search_query:
        query = query.filter(Event.description.ilike(f"%{search_query}%"))
    if min_severity is not None:
        query = query.filter(Event.severity >= min_severity)

    events = query.order_by(Event.id.desc()).limit(limit).all()
    session.close()

    return [
        EventResponse(
            id=e.id, description=e.description,
            event_type=e.event_type, severity=e.severity,
            created_at=e.created_at,
            affected_citizens=e.affected_citizens,
        )
        for e in events
    ]


@router.get("/events/types", response_model=List[str])
async def get_event_types():
    """Return all distinct event_type values present in the events table."""
    from autosociety.backend.core.database import Event, SessionLocal
    session = SessionLocal()
    types = (
        session.query(Event.event_type)
        .distinct()
        .order_by(Event.event_type)
        .all()
    )
    session.close()
    return [t[0] for t in types if t[0]]


@router.get("/analytics", response_model=AnalyticsListResponse)
async def get_analytics():
    """Return all historical metric snapshots for the current run."""
    snapshots = get_all_snapshots()
    return AnalyticsListResponse(
        snapshots=[
            AnalyticsResponse(
                tick=s.tick,
                simulation_day=s.simulation_day if s.simulation_day is not None else s.tick,
                population=s.population,
                avg_happiness=s.avg_happiness,
                avg_wealth=s.avg_wealth,
                gdp=s.gdp,
                crime_rate=s.crime_rate,
                employment_rate=s.employment_rate,
                tax_revenue=s.tax_revenue,
                active_businesses=s.active_businesses,
                political_stability=s.political_stability,
                economic_health=s.economic_health,
            )
            for s in snapshots
        ],
    )


@router.get("/backups", response_model=List[BackupInfo])
async def get_backups():
    """List all available database backup files."""
    from autosociety.backend.core.backup import list_backups
    return [BackupInfo(**b) for b in list_backups()]


@router.get("/analytics/historical", response_model=List[HistoricalSnapshotResponse])
async def get_historical_analytics():
    """
    Merge tick snapshots from all backup runs into a unified timeline.
    Each snapshot carries a run_label so charts can colour-code by run.
    """
    from autosociety.backend.core.backup import merge_all_historical_snapshots
    rows = merge_all_historical_snapshots()
    results = []
    for row in rows:
        results.append(HistoricalSnapshotResponse(
            tick=row.get("tick", 0),
            simulation_day=row.get("simulation_day") or row.get("tick", 0),
            run_label=row.get("run_label", "Unknown Run"),
            population=row.get("population", 0),
            avg_happiness=row.get("avg_happiness"),
            avg_wealth=row.get("avg_wealth"),
            gdp=row.get("gdp"),
            crime_rate=row.get("crime_rate"),
            employment_rate=row.get("employment_rate"),
            tax_revenue=row.get("tax_revenue"),
            active_businesses=row.get("active_businesses"),
            political_stability=row.get("political_stability"),
            economic_health=row.get("economic_health"),
        ))
    return results


@router.get("/reports")
async def get_reports():
    """Return summary report of current world state."""
    session = get_session()
    # get_or_create_world_state commits, expiring prior loads — read it first
    world = get_or_create_world_state(session)
    citizens = list_citizens(session)
    total = len(citizens)
    session.close()

    if total == 0:
        return {"message": "No citizens in the world"}

    return {
        "total_population": total,
        "average_happiness": round(sum(c.happiness for c in citizens) / total, 2),
        "average_wealth": round(sum(c.wealth for c in citizens) / total, 2),
        "average_health": round(sum(c.health for c in citizens) / total, 2),
        "employment_rate": round(sum(1 for c in citizens if c.job) / total, 4),
        "political_stability": world.political_stability,
        "economic_health": world.economic_health,
        "simulation_day": world.simulation_day,
    }
