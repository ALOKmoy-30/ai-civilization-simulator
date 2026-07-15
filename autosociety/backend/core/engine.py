"""
Simulation Engine — runs the game loop on a background asyncio task.
One tick = one simulated day. Offloads all CrewAI blocking calls to a thread pool.
Includes hardware pacing for CPU-only Ollama inference.
"""

import asyncio
import logging
import os
import time
from typing import Optional, Dict, Any, Set

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

# Hardware pacing — every citizen dispatch goes through a single sequential
# channel to prevent CPU contention from concurrent local model inference.
AGENT_DISPATCH_DELAY = int(os.getenv("AGENT_DISPATCH_DELAY_SECONDS", "2"))


class SimulationEngine:
    """Holds simulation state and runs the background tick loop."""

    def __init__(self):
        self._running = False
        self._paused = False
        self._tick = 0
        self._task: Optional[asyncio.Task] = None
        self._scheduler: Optional[ActionScheduler] = None
        self._lock = asyncio.Lock()
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
        if self._running:
            logger.warning("Simulation already running")
            return
        # Fresh start from tick 0 — clear stale events from any previous run
        if self._tick == 0:
            self._clear_stale_events()
        self._running = True
        self._paused = False
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Simulation started")

    def pause(self):
        self._paused = True
        logger.info("Simulation paused")

    def resume(self):
        self._paused = False
        logger.info("Simulation resumed")

    def stop(self):
        self._running = False
        self._paused = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Simulation stopped")

    def reset(self):
        self._tick = 0
        self._scheduler = None
        self._last_gdp = 0.0
        self._last_crime_rate = 0.0
        self._last_active_businesses = 0
        logger.info("Simulation reset")

    def get_state(self) -> Dict[str, Any]:
        session = get_session()
        world = get_or_create_world_state(session)
        citizens = list_citizens(session)
        n = len(citizens)
        avg_h = sum(c.happiness for c in citizens) / n if n else 0
        avg_w = sum(c.wealth for c in citizens) / n if n else 0
        avg_he = sum(c.health for c in citizens) / n if n else 0
        employed = sum(1 for c in citizens if c.job) / n if n else 0
        session.close()
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
        await asyncio.sleep(0)
        await asyncio.to_thread(init_db)
        await asyncio.to_thread(init_metrics_db)
        population = await asyncio.to_thread(self._get_population)
        self._scheduler = ActionScheduler(population)
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

    def _sync_advance_tick(self):
        session = get_session()
        citizens = list_citizens(session)
        if not citizens:
            session.close()
            return None
        total_gdp = 0.0
        total_tax = 0.0
        crime_events = 0
        disaster_type = should_disaster_occur()
        if disaster_type:
            result = apply_disaster(disaster_type)
            logger.info("Tick %d: %s", self._tick, result["description"])
        for citizen in citizens:
            wage = calculate_wage(citizen.job, 50.0)
            tax = calculate_tax(wage)
            wealth_tax = calculate_wealth_tax(citizen.wealth)
            net_income = wage - tax - wealth_tax
            # Simulate crime: unhappy/poor citizens more likely to commit crime
            crime_prob = max(0, 0.02 - citizen.happiness * 0.0003) + max(0, 0.01 - citizen.wealth * 0.00002)
            if __import__('random').random() < crime_prob:
                crime_events += 1
                fine = citizen.wealth * 0.1
                update_citizen(session, citizen.id, {
                    "wealth": round(max(0, citizen.wealth - fine), 2),
                    "happiness": round(max(0, citizen.happiness - 5), 2),
                })
            else:
                update_citizen(session, citizen.id, {
                    "wealth": round(max(0, citizen.wealth + net_income), 2),
                })
            total_gdp += wage
            total_tax += tax + wealth_tax
        world = get_or_create_world_state(session)
        update_world_state(session, {
            "simulation_day": world.simulation_day + 1,
            "total_wealth": world.total_wealth + total_gdp,
        })
        session.close()
        return {"total_gdp": total_gdp, "crime_rate": crime_events / max(1, len(citizens)),
                "tax_revenue": total_tax}

    async def _advance_tick(self):
        self._tick += 1
        reasoning_set = self._scheduler.tick() if self._scheduler else set()
        result = await asyncio.to_thread(self._sync_advance_tick)
        if result is None:
            return
        self._last_gdp = result["total_gdp"]
        self._last_crime_rate = result["crime_rate"]
        self._last_active_businesses = 0
        tax_revenue = result.get("tax_revenue", 0)
        record_snapshot(
            tick=self._tick, gdp=self._last_gdp,
            crime_rate=self._last_crime_rate, tax_revenue=tax_revenue,
            active_businesses=0,
        )
        if reasoning_set:
            await self._run_reasoning_batch(reasoning_set)
        if self._tick % cfg.TICKS_PER_MONTH == 0:
            await self._run_government_session()

    # ── Prompt-length guard ───────────────────────────────────────

    def _truncate_memory_context(self, task_description: str,
                                  memory_text: str, max_tokens: int = 1800) -> str:
        """Truncate memory context so the full prompt fits in the context window."""
        prompt_estimate = len(task_description) + len(memory_text)
        if prompt_estimate > max_tokens * 4:  # rough char→token ratio
            available = max_tokens * 4 - len(task_description)
            if available < 200:
                return ""
            return memory_text[:available]
        return memory_text

    def _clear_stale_events(self):
        """Delete all events — called when simulation starts fresh from tick 0."""
        try:
            from autosociety.backend.core.database import Event, SessionLocal
            s = SessionLocal()
            s.query(Event).delete()
            s.commit()
            s.close()
            logger.info("Cleared stale events from previous run")
        except Exception:
            pass

    # ── Reasoning dispatch (sequential, paced) ───────────────────

    async def _run_reasoning_batch(self, citizen_ids: Set[int]):
        """Run CrewAI reasoning for selected citizens.
        Strictly sequential — one at a time — for CPU-only local inference.
        Logs wall-clock time per citizen and total batch duration.
        Logs a success event for each citizen that completes and a failure
        event for each that errors, so the events feed shows activity.
        """
        from autosociety.agents.crews.citizen import run_citizen_decision

        total = len(citizen_ids)
        batch_start = time.monotonic()
        per_citizen_times = []

        for i, cid in enumerate(sorted(citizen_ids), 1):
            citizen_start = time.monotonic()
            try:
                logger.info("Citizen %d reasoning (%d/%d)...", cid, i, total)
                decision = await asyncio.to_thread(
                    run_citizen_decision,
                    cid,
                    f"Day {self._tick} of society life. Go about your daily business.",
                )
                elapsed = time.monotonic() - citizen_start
                per_citizen_times.append(elapsed)
                logger.info("Citizen %d done in %.1fs", cid, elapsed)
                try:
                    s = get_session()
                    action_preview = decision.get("readable_action") or str(decision.get("decision", ""))[:200]
                    citizen_name = decision.get("name", f"Citizen {cid}")
                    effects_info = decision.get("effects", {})
                    h_delta = effects_info.get("happiness_delta", 0)
                    w_delta = effects_info.get("wealth_delta", 0)
                    create_event(s,
                        description=(
                            f"[Citizen #{cid} | {citizen_name}] {action_preview} "
                            f"[Effects: Happiness {h_delta:+,}, Wealth ${w_delta:+,}]"
                        ),
                        event_type="citizen_action", severity=1,
                    )
                    s.close()
                except Exception:
                    pass

            except TimeoutError as e:
                elapsed = time.monotonic() - citizen_start
                per_citizen_times.append(elapsed)
                logger.warning(
                    "Citizen %d timed out after %.1fs (model too slow — "
                    "consider reducing context or switching model)",
                    cid, elapsed,
                )
                try:
                    s = get_session()
                    create_event(s,
                        description=(
                            f"[Citizen #{cid}] LLM timed out "
                            f"after {elapsed:.0f}s. Skipping decision this tick."
                        ),
                        event_type="agent_timeout", severity=2,
                    )
                    s.close()
                except Exception:
                    pass

            except Exception as e:
                # Catches context-window overflow (litellm.ContextWindowExceededError),
                # model-not-found errors, and any other unexpected failures.
                elapsed = time.monotonic() - citizen_start
                per_citizen_times.append(elapsed)
                err_type = type(e).__name__
                is_ctx = "context" in str(e).lower() or "window" in str(e).lower()
                if is_ctx:
                    logger.warning(
                        "Citizen %d context window exceeded after %.1fs "
                        "(prompt too long for 0.5B model — memory will be truncated next tick)",
                        cid, elapsed,
                    )
                else:
                    logger.warning(
                        "Citizen %d reasoning failed after %.1fs: %s",
                        cid, elapsed, e, exc_info=True,
                    )
                try:
                    s = get_session()
                    create_event(s,
                        description=(
                            f"[Citizen #{cid}] Unable to make a decision today. "
                            f"(Error: {err_type}: {e})"
                        ),
                        event_type="agent_failure", severity=2,
                    )
                    s.close()
                except Exception:
                    pass

            if i < total:
                await asyncio.sleep(AGENT_DISPATCH_DELAY)

        batch_elapsed = time.monotonic() - batch_start
        if per_citizen_times:
            avg = sum(per_citizen_times) / len(per_citizen_times)
            logger.info(
                "Reasoning batch done: %d/%d citizens, total %.1fs, "
                "avg %.1fs per citizen",
                len(per_citizen_times), total, batch_elapsed, avg,
            )

    async def _run_government_session(self):
        from autosociety.agents.crews.government import GovernmentCrew
        logger.info("Tick %d: Government policy session starting...", self._tick)
        try:
            result = await asyncio.to_thread(
                self._sync_government_session,
                f"Monthly review at day {self._tick}.",
            )
            logger.info(
                "Government enacted policy: %s (effects: %s)",
                result.get("name", "Unknown"),
                result.get("effects", {}),
            )
        except Exception as e:
            logger.warning(
                "Government policy session failed: %s", e, exc_info=True,
            )
            try:
                s = get_session()
                create_event(s,
                    description=(
                        "Government session failed. "
                        f"(Error: {type(e).__name__}: {e})"
                    ),
                    event_type="government_failure", severity=3,
                )
                s.close()
            except Exception:
                pass

    def _sync_government_session(self, situation: str) -> Dict[str, Any]:
        from autosociety.agents.crews.government import GovernmentCrew
        gov = GovernmentCrew()
        return gov.decide_policy(situation)
