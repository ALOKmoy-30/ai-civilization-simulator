import asyncio
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from autosociety.backend.core.engine import SimulationEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulation", tags=["simulation"])


# ── Pydantic models ─────────────────────────────────────────────────

class WorldStateResponse(BaseModel):
    tick: int
    running: bool
    paused: bool
    population: int
    avg_happiness: float
    avg_wealth: float
    avg_health: float
    employment_rate: float
    gdp: float
    crime_rate: float
    active_businesses: int
    political_stability: float
    economic_health: float
    simulation_day: int


class StatusResponse(BaseModel):
    status: str
    message: str


# ── Dependency: engine singleton ────────────────────────────────────

_engine: SimulationEngine = None

def set_engine(engine: SimulationEngine):
    global _engine
    _engine = engine

def get_engine() -> SimulationEngine:
    global _engine
    return _engine


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/state", response_model=WorldStateResponse)
async def get_world_state():
    """Return current simulation world state."""
    eng = get_engine()
    # Run the sync DB work in a thread so it doesn't block the event loop
    state = await asyncio.to_thread(eng.get_state)
    return WorldStateResponse(**state)


@router.post("/start", response_model=StatusResponse)
async def start_simulation():
    """Start the simulation background loop."""
    eng = get_engine()
    if eng.is_running:
        return StatusResponse(status="ok", message="Simulation is already running")
    eng.start()
    return StatusResponse(status="ok", message="Simulation started")


@router.post("/pause", response_model=StatusResponse)
async def pause_simulation():
    """Pause the simulation. Tick progression stops."""
    eng = get_engine()
    if not eng.is_running:
        return StatusResponse(status="ok", message="Simulation is not running")
    if eng.is_paused:
        return StatusResponse(status="ok", message="Simulation is already paused")
    eng.pause()
    return StatusResponse(status="ok", message="Simulation paused")


@router.post("/resume", response_model=StatusResponse)
async def resume_simulation():
    """Resume a paused simulation."""
    eng = get_engine()
    if not eng.is_running:
        return StatusResponse(status="ok", message="Simulation is not running")
    if not eng.is_paused:
        return StatusResponse(status="ok", message="Simulation is not paused")
    eng.resume()
    return StatusResponse(status="ok", message="Simulation resumed")


@router.post("/stop", response_model=StatusResponse)
async def stop_simulation():
    """Stop the simulation entirely."""
    eng = get_engine()
    if not eng.is_running:
        return StatusResponse(status="ok", message="Simulation is not running")
    eng.stop()
    return StatusResponse(status="ok", message="Simulation stopped")


@router.post("/reset", response_model=StatusResponse)
async def reset_simulation():
    """Reset simulation to tick 0 and archive previous run."""
    eng = get_engine()
    if eng.is_running:
        eng.stop()

    # Create a backup of the completed run before resetting
    try:
        from autosociety.backend.core.backup import create_backup
        create_backup(label="reset")
    except Exception as e:
        logger.warning("Backup before reset failed: %s", e)

    eng.reset()

    # Clear metrics table for the fresh run so ticks start cleanly from 0
    try:
        from autosociety.backend.core.metrics import metrics_engine, text
        with metrics_engine.connect() as conn:
            conn.execute(text("DELETE FROM tick_snapshots"))
            conn.commit()
    except Exception as e:
        logger.warning("Clearing metrics table on reset failed: %s", e)

    return StatusResponse(status="ok", message="Simulation reset to tick 0 and run archived")
