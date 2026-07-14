"""
Simulation Engine — runs the game loop on a background asyncio task.
One tick = one simulated day. Offloads all CrewAI blocking calls to a thread pool.
"""

import asyncio
import logging
import random
from typing import Optional, Dict, Any

from autosociety.backend.core.database import (
    init_db, get_session, get_or_create_world_state, update_world_state,
    list_citizens, update_citizen, create_event,
)
from autosociety.backend.core.scheduler import ActionScheduler
from autosociety.backend.core.metrics import init_metrics_db, record_snapshot
from autosociety.backend.core.config import world_config as cfg
from autosociety.backend.core.world_rules import calculate_wage, calculate_tax, calculate_wealth_tax
from autosociety.backend.core.disasters import should_disaster_occur, apply_disaster

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Holds simulation state and runs the background tick loop."""

    def __init__(self):
        self._running = False
        self._paused = False
        self._tick = 0
        self._task: Optional[asyncio.Task] = None
        self._scheduler: Optional[ActionScheduler] = None
        self._lock = asyncio.Lock()
        # Estimate gdp/crime/businesses from last tick for get_state
        self._last_gdp = 0.0
        self._last_crime_rate = 0.0
        self._last_active_businesses = 0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def current_tick(self) -> int:
        return self._tick

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self):
        """Start the simulation background loop."""
        if self._running:
            logger.warning("Simulation already running")
            return
        self._running = True
        self._paused = False
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Simulation started")

    def pause(self):
        """Pause tick progression."""
        self._paused = True
        logger.info("Simulation paused")

    def resume(self):
        """Resume from paused state."""
        self._paused = False
        logger.info("Simulation resumed")

    def stop(self):
        """Stop the simulation entirely."""
        self._running = False
        self._paused = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Simulation stopped")

    def reset(self):
        """Reset to tick 0. Requires sim to be stopped."""
        self._tick = 0
        self._scheduler = None
        self._last_gdp = 0.0
        self._last_crime_rate = 0.0
        self._last_active_businesses = 0
        logger.info("Simulation reset")

    def get_state(self) -> Dict[str, Any]:
        """Return current simulation state as a dict."""
        session = get_session()
        # get_or_create_world_state commits, which expires session objects —
        # so read it BEFORE loading citizens to avoid detach issues
        world = get_or_create_world_state(session)
        citizens = list_citizens(session)

        n = len(citizens)
        avg_h = sum(c.happiness for c in citizens) / n if n else 0
        avg_w = sum(c.wealth for c in citizens) / n if n else 0
        avg_he = sum(c.health for c in citizens) / n if n else 0
        employed = sum(1 for c in citizens if c.job) / n if n else 0

        return {
            "tick": self._tick,
            "running": self._running,
            "paused": self._paused,
            "population": n,
            "avg_happiness": round(avg_h, 2),
            "avg_wealth": round(avg_w, 2),
            "avg_health": round(avg_he, 2),
            "employment_rate": round(employed, 4),
            "gdp": round(self._last_gdp, 2),
            "crime_rate": round(self._last_crime_rate, 4),
            "active_businesses": self._last_active_businesses,
            "political_stability": round(world.political_stability, 2),
            "economic_health": round(world.economic_health, 2),
            "simulation_day": world.simulation_day,
        }

    # ── Background loop ───────────────────────────────────────────

    async def _run_loop(self):
        """Main simulation loop. Runs until stopped."""
        init_db()
        init_metrics_db()

        self._scheduler = ActionScheduler(self._get_population())

        while self._running:
            if self._paused:
                await asyncio.sleep(0.5)
                continue

            await self._advance_tick()
            await asyncio.sleep(1.0)

        logger.info("Simulation loop ended")

    def _get_population(self) -> int:
        try:
            session = get_session()
            from autosociety.backend.core.database import list_citizens
            c = list_citizens(session)
            session.close()
            return len(c)
        except Exception:
            return 0

    async def _advance_tick(self):
        """Execute one tick's worth of world updates."""
        self._tick += 1
        reasoning_set = self._scheduler.tick()

        session = get_session()
        citizens = list_citizens(session)
        session.close()

        if not citizens:
            return

        total_gdp = 0.0
        crime_events = 0

        disaster_type = should_disaster_occur()
        if disaster_type:
            result = apply_disaster(disaster_type)
            logger.info("Tick %d: %s", self._tick, result["description"])

        # Lightweight deterministic updates for ALL citizens
        for citizen in citizens:
            wage = calculate_wage(citizen.job, 50.0)
            tax = calculate_tax(wage)
            wealth_tax = calculate_wealth_tax(citizen.wealth)
            net_income = wage - tax - wealth_tax

            s = get_session()
            update_citizen(s, citizen.id, {
                "wealth": round(max(0, citizen.wealth + net_income), 2),
            })
            s.close()
            total_gdp += wage

        # Full reasoning for selected citizens (offloaded to thread pool)
        if reasoning_set:
            await self._run_reasoning_batch(reasoning_set)

        # Update world state
        session = get_session()
        world = get_or_create_world_state(session)
        update_world_state(session, {
            "simulation_day": world.simulation_day + 1,
            "total_wealth": world.total_wealth + total_gdp,
        })
        session.close()

        self._last_gdp = total_gdp
        self._last_crime_rate = crime_events / max(1, len(citizens))
        self._last_active_businesses = 0

        record_snapshot(
            tick=self._tick,
            gdp=total_gdp,
            crime_rate=self._last_crime_rate,
            tax_revenue=0,
            active_businesses=0,
        )

    async def _run_reasoning_batch(self, citizen_ids):
        """Run CrewAI reasoning for selected citizens in thread pool."""
        from autosociety.agents.crews.citizen import run_citizen_decision

        for cid in citizen_ids:
            try:
                await asyncio.to_thread(
                    run_citizen_decision,
                    cid,
                    f"Day {self._tick} of society life. Go about your daily business.",
                )
            except Exception as e:
                logger.warning("Citizen %d reasoning failed: %s", cid, e)
