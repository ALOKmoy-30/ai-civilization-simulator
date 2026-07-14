"""
Deterministic world rule functions.
All math lives here — LLMs decide intent, these compute the numbers.
"""

import random
import math
from typing import Optional, Tuple

from autosociety.backend.core.config import world_config as cfg


# ── Taxation ────────────────────────────────────────────────────────

def calculate_tax(income: float, rate: Optional[float] = None) -> float:
    """Progressive income tax. Returns tax amount."""
    if rate is not None:
        return round(income * rate, 2)

    if income <= cfg.TAX_THRESHOLD_LOW:
        return round(income * cfg.TAX_RATE_LOW, 2)
    elif income >= cfg.TAX_THRESHOLD_HIGH:
        return round(income * cfg.TAX_RATE_HIGH, 2)
    else:
        return round(income * cfg.BASE_TAX_RATE, 2)


def calculate_wealth_tax(wealth: float) -> float:
    """Daily wealth tax (annual rate / ticks per month / 12)."""
    daily_rate = cfg.WEALTH_TAX_RATE / (cfg.TICKS_PER_MONTH * 12)
    return round(wealth * daily_rate, 2)


# ── Wages ───────────────────────────────────────────────────────────

def calculate_wage(job: str, skill_level: float) -> float:
    """Daily wage based on job and skill. """
    base = cfg.JOB_WAGES.get(job, 40)
    skill_mult = 0.5 + (skill_level / 200.0)  # ranges ~0.5 to 1.0
    return round(base * skill_mult, 2)


# ── Skills ──────────────────────────────────────────────────────────

def skill_progression(current_level: float, hours_invested: float,
                      education_budget: float = 0) -> float:
    """New skill level after investing hours."""
    budget_mult = 1.0 + education_budget * cfg.EDUCATION_BUDGET_EFFECT
    gain = hours_invested * cfg.SKILL_GAIN_PER_HOUR * budget_mult
    decay = cfg.SKILL_BASE_DECAY * (current_level / cfg.SKILL_MAX)
    new_level = current_level + gain - decay
    return round(max(0, min(cfg.SKILL_MAX, new_level)), 2)


# ── Business ─────────────────────────────────────────────────────────

def business_outcome(capital: float, business_type: str,
                     local_demand: float) -> Tuple[float, float]:
    """Returns (revenue, health_change) for one tick."""
    required = cfg.BUSINESS_CAPITAL_REQUIREMENTS.get(business_type, 2000)
    base_rev = cfg.BUSINESS_BASE_REVENUE.get(business_type, 100)

    if capital < required:
        # Underfunded — lower revenue, health declines
        funding_ratio = capital / required
        revenue = round(base_rev * funding_ratio * local_demand, 2)
        health_change = -0.5 * (1 - funding_ratio)
        return revenue, health_change

    revenue = round(base_rev * local_demand * (1 + (capital - required) / required * 0.1), 2)
    overhead = revenue * cfg.BUSINESS_OVERHEAD_RATE
    profit = revenue - overhead
    health_change = round(profit / revenue if revenue > 0 else -0.5, 2)
    health_change = max(-5.0, min(5.0, health_change))
    return revenue, health_change


# ── Marriage ─────────────────────────────────────────────────────────

def marriage_compatibility(citizen_a: dict, citizen_b: dict) -> float:
    """Score 0-1 of how compatible two citizens are."""
    age_diff = abs(citizen_a.get("age", 30) - citizen_b.get("age", 30))
    age_score = max(0, 1 - age_diff / 40)

    happiness_sim = 1 - abs(
        citizen_a.get("happiness", 50) - citizen_b.get("happiness", 50)
    ) / 100

    social_sim = 1 - abs(
        citizen_a.get("social_score", 50) - citizen_b.get("social_score", 50)
    ) / 100

    wealth_gap = abs(citizen_a.get("wealth", 100) - citizen_b.get("wealth", 100))
    wealth_score = max(0, 1 - wealth_gap / 500)

    score = 0.30 * age_score + 0.25 * happiness_sim + 0.25 * social_sim + 0.20 * wealth_score
    return round(score, 3)


# ── Crime ───────────────────────────────────────────────────────────

def crime_base_probability(crime_type: str) -> float:
    """Base probability of a crime type occurring."""
    return cfg.CRIME_BASE_PROBABILITIES.get(crime_type, 0.05)


def crime_attempt_probability(citizen: dict, crime_type: str) -> float:
    """Probability a specific citizen attempts a crime."""
    base = crime_base_probability(crime_type)
    wealth_mod = citizen.get("wealth", 100) * cfg.CRIME_WEALTH_MODIFIER
    happiness = citizen.get("happiness", 50)
    happiness_mod = max(0, 50 - happiness) * cfg.CRIME_HAPPINESS_MODIFIER
    prob = base + wealth_mod + happiness_mod
    return round(max(0.001, min(0.5, prob)), 4)


def crime_outcome(citizen_wealth: float, crime_type: str,
                  law_enforcement_budget: float) -> Tuple[bool, float]:
    """Returns (caught, fine_if_caught) for a crime attempt."""
    detection_rate = cfg.POLICE_BASE_EFFECTIVENESS + law_enforcement_budget * cfg.POLICE_BUDGET_EFFECTIVENESS
    detection_rate = min(0.95, detection_rate)

    caught = random.random() < detection_rate
    if caught:
        fine = round(citizen_wealth * cfg.CRIME_PUNISHMENT_SEVERITY * random.uniform(0.3, 1.0), 2)
    else:
        fine = 0.0
    return caught, fine


# ── Travel ───────────────────────────────────────────────────────────

def travel_effects(citizen: dict, destination: str,
                   duration_days: int) -> dict:
    """Compute effects of a travel action. Returns stat changes."""
    cost = round(citizen.get("wealth", 100) * cfg.TRAVEL_COST_MULTIPLIER * duration_days, 2)
    happiness_boost = cfg.TRAVEL_HAPPINESS_BOOST * min(1.0, duration_days / 5)
    return {
        "wealth_delta": -cost,
        "happiness_delta": round(happiness_boost, 1),
        "days_occupied": duration_days,
    }
