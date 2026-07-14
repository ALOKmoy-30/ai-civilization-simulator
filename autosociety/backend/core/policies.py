"""
Policy effect functions.
Government crew decides WHICH policy to enact; these compute the deterministic effects.
"""

from typing import Dict, Any
from autosociety.backend.core.config import world_config as cfg


def apply_tax_change(new_rate: float) -> Dict[str, Any]:
    """Change the base tax rate. Returns a description of changes."""
    old_rate = cfg.BASE_TAX_RATE
    cfg.BASE_TAX_RATE = max(0.0, min(0.5, new_rate))
    return {
        "parameter": "BASE_TAX_RATE",
        "old_value": old_rate,
        "new_value": cfg.BASE_TAX_RATE,
        "description": f"Base tax rate changed from {old_rate:.0%} to {cfg.BASE_TAX_RATE:.0%}",
    }


def apply_budget_reallocation(health_budget: float, education_budget: float,
                               police_budget: float) -> Dict[str, Any]:
    """Reallocate government budget. Returns description."""
    from types import SimpleNamespace
    # Stored as module-level config values for the rule functions to read
    cfg.HEALTH_BUDGET_CURRENT = max(0, health_budget)
    cfg.EDUCATION_BUDGET_CURRENT = max(0, education_budget)
    cfg.POLICE_BUDGET_CURRENT = max(0, police_budget)
    return {
        "parameter": "budget_allocation",
        "new_value": {
            "health": cfg.HEALTH_BUDGET_CURRENT,
            "education": cfg.EDUCATION_BUDGET_CURRENT,
            "police": cfg.POLICE_BUDGET_CURRENT,
        },
        "description": (
            f"Budget reallocated — health: {health_budget:.0f}, "
            f"education: {education_budget:.0f}, police: {police_budget:.0f}"
        ),
    }


def apply_emergency_relief(amount: float) -> Dict[str, Any]:
    """Distribute emergency relief funds. Returns per-citizen amount."""
    from autosociety.backend.core.config.world_config import NEW_CITIZEN_STATS
    return {
        "parameter": "emergency_relief",
        "old_value": 0,
        "new_value": amount,
        "description": f"Emergency relief of {amount:.0f} currency units distributed",
    }


def apply_wealth_tax_change(new_rate: float) -> Dict[str, Any]:
    """Change the wealth tax rate."""
    old_rate = cfg.WEALTH_TAX_RATE
    cfg.WEALTH_TAX_RATE = max(0.0, min(0.1, new_rate))
    return {
        "parameter": "WEALTH_TAX_RATE",
        "old_value": old_rate,
        "new_value": cfg.WEALTH_TAX_RATE,
        "description": f"Wealth tax rate changed from {old_rate:.2%} to {cfg.WEALTH_TAX_RATE:.2%}",
    }


def get_all_policy_descriptions() -> Dict[str, str]:
    """Return descriptions of all available policies for the Government crew."""
    return {
        "tax_change": "Change the base income tax rate (0.0 to 0.5). Provide new_rate as float.",
        "budget_reallocation": "Reallocate budget across health, education, and police. Provide health_budget, education_budget, police_budget.",
        "emergency_relief": "Distribute emergency relief funds. Provide amount as float.",
        "wealth_tax_change": "Change the wealth tax rate (0.0 to 0.1). Provide new_rate as float.",
    }
