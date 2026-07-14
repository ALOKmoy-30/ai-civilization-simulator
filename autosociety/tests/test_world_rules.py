"""
Unit tests for world_rules.py — deterministic expected outputs.
"""

import pytest
from autosociety.backend.core.world_rules import (
    calculate_tax,
    calculate_wealth_tax,
    calculate_wage,
    skill_progression,
    business_outcome,
    marriage_compatibility,
    crime_attempt_probability,
    travel_effects,
)
from autosociety.backend.core.config import world_config as cfg


class TestTaxation:
    def test_low_income_uses_reduced_rate(self):
        tax = calculate_tax(50.0)
        assert tax == 50.0 * cfg.TAX_RATE_LOW  # 50 * 0.05 = 2.5

    def test_mid_income_uses_base_rate(self):
        tax = calculate_tax(200.0)
        assert tax == 200.0 * cfg.BASE_TAX_RATE  # 200 * 0.15 = 30.0

    def test_high_income_uses_higher_rate(self):
        tax = calculate_tax(500.0)
        assert tax == 500.0 * cfg.TAX_RATE_HIGH  # 500 * 0.25 = 125.0

    def test_custom_rate_overrides_progressive(self):
        tax = calculate_tax(200.0, rate=0.10)
        assert tax == 20.0

    def test_zero_income(self):
        assert calculate_tax(0) == 0.0

    def test_wealth_tax_is_small_fraction(self):
        tax = calculate_wealth_tax(1000.0)
        daily_rate = cfg.WEALTH_TAX_RATE / (cfg.TICKS_PER_MONTH * 12)
        assert tax == round(1000.0 * daily_rate, 2)


class TestWages:
    def test_known_job_wage(self):
        wage = calculate_wage("Engineer", skill_level=50.0)
        base = cfg.JOB_WAGES["Engineer"]
        skill_mult = 0.5 + (50.0 / 200.0)
        expected = round(base * skill_mult, 2)
        assert wage == expected

    def test_unknown_job_uses_default(self):
        wage = calculate_wage("UnknownJob", skill_level=50.0)
        assert wage == round(40 * (0.5 + 50.0 / 200.0), 2)

    def test_higher_skill_higher_wage(self):
        low = calculate_wage("Doctor", skill_level=20.0)
        high = calculate_wage("Doctor", skill_level=80.0)
        assert high > low


class TestSkills:
    def test_skill_progression_no_investment(self):
        result = skill_progression(50.0, 0)
        assert result < 50.0  # decay

    def test_skill_progression_with_study(self):
        result = skill_progression(50.0, 10)
        assert result > 50.0  # gain > decay

    def test_skill_capped_at_max(self):
        result = skill_progression(cfg.SKILL_MAX, 1000)
        assert result <= cfg.SKILL_MAX

    def test_budget_boosts_progression(self):
        no_budget = skill_progression(50.0, 10, education_budget=0)
        with_budget = skill_progression(50.0, 10, education_budget=100)
        assert with_budget > no_budget


class TestBusiness:
    def test_underfunded_business_loses_health(self):
        rev, health = business_outcome(
            capital=100, business_type="technology", local_demand=1.0
        )
        assert rev < cfg.BUSINESS_BASE_REVENUE["technology"]
        assert health < 0

    def test_well_funded_business_profitable(self):
        rev, health = business_outcome(
            capital=10000, business_type="technology", local_demand=1.0
        )
        assert rev > 0
        assert health > 0

    def test_low_demand_reduces_revenue(self):
        high_demand = business_outcome(5000, "retail", local_demand=1.5)
        low_demand = business_outcome(5000, "retail", local_demand=0.5)
        assert high_demand[0] > low_demand[0]


class TestMarriage:
    def test_identical_citizens_high_score(self):
        a = {"age": 30, "happiness": 70, "social_score": 60, "wealth": 200}
        b = {"age": 30, "happiness": 70, "social_score": 60, "wealth": 200}
        score = marriage_compatibility(a, b)
        assert 0.9 <= score <= 1.0

    def test_very_different_citizens_low_score(self):
        a = {"age": 20, "happiness": 90, "social_score": 90, "wealth": 500}
        b = {"age": 60, "happiness": 10, "social_score": 10, "wealth": 10}
        score = marriage_compatibility(a, b)
        assert score < 0.6

    def test_score_between_0_and_1(self):
        a = {"age": 35, "happiness": 60, "social_score": 50, "wealth": 150}
        b = {"age": 40, "happiness": 55, "social_score": 45, "wealth": 200}
        score = marriage_compatibility(a, b)
        assert 0 <= score <= 1


class TestCrime:
    def test_happy_wealthy_citizen_low_probability(self):
        citizen = {"wealth": 500, "happiness": 80}
        prob = crime_attempt_probability(citizen, "theft")
        assert prob < cfg.CRIME_BASE_PROBABILITIES["theft"]

    def test_unhappy_poor_citizen_higher_probability(self):
        citizen = {"wealth": 10, "happiness": 20}
        prob = crime_attempt_probability(citizen, "theft")
        assert prob > cfg.CRIME_BASE_PROBABILITIES["theft"]

    def test_probability_clamped(self):
        citizen = {"wealth": 0, "happiness": 0}
        prob = crime_attempt_probability(citizen, "theft")
        assert prob <= 0.5


class TestTravel:
    def test_travel_costs_wealth(self):
        citizen = {"wealth": 100}
        effects = travel_effects(citizen, "beach", duration_days=3)
        assert effects["wealth_delta"] < 0

    def test_travel_boosts_happiness(self):
        citizen = {"wealth": 100}
        effects = travel_effects(citizen, "beach", duration_days=3)
        assert effects["happiness_delta"] > 0

    def test_longer_trip_bigger_boost(self):
        citizen = {"wealth": 1000}
        short = travel_effects(citizen, "city", duration_days=1)
        long = travel_effects(citizen, "city", duration_days=5)
        assert long["happiness_delta"] > short["happiness_delta"]

    def test_trip_occupies_days(self):
        citizen = {"wealth": 100}
        effects = travel_effects(citizen, "city", duration_days=3)
        assert effects["days_occupied"] == 3
