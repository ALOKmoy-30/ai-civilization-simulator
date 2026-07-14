"""Query endpoints — read-only access to simulation data."""

from typing import List, Optional

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
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EventResponse(BaseModel):
    id: int
    description: str
    event_type: str
    severity: int
    created_at: datetime


class AnalyticsResponse(BaseModel):
    tick: int
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


@router.get("/policies", response_model=List[PolicyResponse])
async def get_policies():
    """List all policies."""
    from autosociety.backend.core.database import list_policies
    session = get_session()
    policies = list_policies(session)
    session.close()
    return [
        PolicyResponse(
            id=p.id, name=p.name, description=p.description,
            is_active=p.is_active,
            created_at=p.created_at, updated_at=p.updated_at,
        )
        for p in policies
    ]


@router.get("/events", response_model=List[EventResponse])
async def get_events(limit: int = Query(50, ge=1, le=500)):
    """List recent events."""
    from autosociety.backend.core.database import SimulationLog, SessionLocal
    session = SessionLocal()
    events = (
        session.query(SimulationLog)
        .order_by(SimulationLog.id.desc())
        .limit(limit)
        .all()
    )
    session.close()
    return [
        EventResponse(
            id=e.id, description=e.details,
            event_type=e.action, severity=1,
            created_at=e.timestamp,
        )
        for e in events
    ]


@router.get("/analytics", response_model=AnalyticsListResponse)
async def get_analytics():
    """Return all historical metric snapshots."""
    snapshots = get_all_snapshots()
    return AnalyticsListResponse(
        snapshots=[
            AnalyticsResponse(
                tick=s.tick, population=s.population,
                avg_happiness=s.avg_happiness, avg_wealth=s.avg_wealth,
                gdp=s.gdp, crime_rate=s.crime_rate,
                employment_rate=s.employment_rate,
                tax_revenue=s.tax_revenue,
                active_businesses=s.active_businesses,
                political_stability=s.political_stability,
                economic_health=s.economic_health,
            )
            for s in snapshots
        ],
    )


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
