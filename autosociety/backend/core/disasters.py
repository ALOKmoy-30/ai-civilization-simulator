"""
Disaster simulation.
Deterministic effects computed here; LLM only decides response strategy.
"""

import random
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from autosociety.backend.core.config import world_config as cfg
from autosociety.backend.core.database import (
    get_session, create_event, list_citizens, get_citizen, update_citizen,
    get_or_create_world_state, update_world_state, Citizen,
)


DISASTER_TYPES = ["fire", "flood", "recession", "disease_outbreak"]


def should_disaster_occur() -> Optional[str]:
    """Roll for a disaster this tick. Returns disaster type or None."""
    if random.random() < cfg.DISASTER_BASE_PROBABILITY:
        return random.choice(DISASTER_TYPES)
    return None


def apply_disaster(disaster_type: str) -> Dict[str, Any]:
    """
    Apply a disaster to the world. Returns summary of effects.
    Called at the start of a tick if should_disaster_occur() returns a type.
    """
    session = get_session()
    citizens = list_citizens(session)
    world = get_or_create_world_state(session)

    damage_ranges = cfg.DISASTER_DAMAGE_RANGE.get(disaster_type, {})
    num_affected = max(1, int(len(citizens) * cfg.DISASTER_AFFECTED_FRACTION))
    affected = random.sample(citizens, min(num_affected, len(citizens)))

    total_wealth_loss = 0.0
    total_health_loss = 0.0
    total_happiness_loss = 0.0

    for citizen in affected:
        updates = {}
        # Wealth damage
        w_range = damage_ranges.get("wealth", (0, 0))
        if w_range[1] > 0:
            loss_pct = random.uniform(w_range[0], w_range[1])
            loss = round(citizen.wealth * loss_pct, 2)
            updates["wealth"] = round(max(0, citizen.wealth - loss), 2)
            total_wealth_loss += loss

        # Health damage
        h_range = damage_ranges.get("health", (0, 0))
        if h_range[1] > 0:
            loss_pct = random.uniform(h_range[0], h_range[1])
            loss = round(citizen.health * loss_pct, 2)
            updates["health"] = round(max(0, min(100, citizen.health - loss)), 2)
            total_health_loss += loss

        # Happiness damage
        happ_range = damage_ranges.get("happiness", (0, 0))
        if happ_range[1] > 0:
            loss_pct = random.uniform(happ_range[0], happ_range[1])
            loss = round(citizen.happiness * loss_pct, 2)
            updates["happiness"] = round(max(0, min(100, citizen.happiness - loss)), 2)
            total_happiness_loss += loss

        if updates:
            update_citizen(session, citizen.id, updates)

    # Log the event
    event_desc = (
        f"A {disaster_type} has struck! "
        f"{num_affected} citizens affected. "
        f"Total wealth loss: {total_wealth_loss:.0f}, "
        f"health loss: {total_health_loss:.0f}, "
        f"happiness loss: {total_happiness_loss:.0f}."
    )

    event = create_event(
        session,
        description=event_desc,
        event_type="disaster",
        severity=_disaster_severity(disaster_type),
    )

    session.close()

    return {
        "disaster_type": disaster_type,
        "event_id": event.id,
        "citizens_affected": num_affected,
        "total_wealth_loss": round(total_wealth_loss, 2),
        "total_health_loss": round(total_health_loss, 2),
        "total_happiness_loss": round(total_happiness_loss, 2),
        "description": event_desc,
    }


def _disaster_severity(disaster_type: str) -> int:
    """Severity 1-10 based on disaster type."""
    severity_map = {
        "fire": 5,
        "flood": 7,
        "recession": 6,
        "disease_outbreak": 8,
    }
    return severity_map.get(disaster_type, 5)
