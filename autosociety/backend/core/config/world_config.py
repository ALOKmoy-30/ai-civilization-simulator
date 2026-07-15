"""
Tunable simulation parameters.
Students can tweak these for experiments without touching logic code.
"""

# ── Time ────────────────────────────────────────────────────────────
TICKS_PER_MONTH: int = 3

# ── Scheduling ──────────────────────────────────────────────────────
CITIZEN_REASONING_RATE: float = 0.45
# Fraction of citizens that get a full LLM reasoning cycle per tick.
# The rest get a lightweight deterministic update with no LLM call.
# At 0.45, every citizen gets at least one full cycle within 3 ticks.

# ── Job base wages (per tick = per day) ─────────────────────────────
# Values represent daily income in currency units
JOB_WAGES: dict = {
    "Engineer":            75,
    "Doctor":              90,
    "Lawyer":              85,
    "Software Developer":  80,
    "Data Analyst":        70,
    "Manager":             75,
    "Consultant":          78,
    "Scientist":           72,
    "Researcher":          68,
    "Pilot":               88,
    "Architect":           70,
    "Pharmacist":          80,
    "Accountant":          60,
    "Teacher":             50,
    "Nurse":               55,
    "Chef":                45,
    "Artist":              40,
    "Writer":              42,
    "Designer":            55,
    "Electrician":         52,
    "Plumber":             50,
    "Carpenter":           48,
    "Mechanic":            50,
    "Marketing Manager":   65,
    "Sales Rep":           55,
    "Analyst":             58,
    "Producer":            52,
    "Administrator":       48,
    "Technician":          50,
    "Therapist":           58,
}

# ── Taxation ────────────────────────────────────────────────────────
BASE_TAX_RATE: float = 0.15          # flat income tax rate
TAX_THRESHOLD_LOW: float = 100.0     # below this, reduced rate applies
TAX_RATE_LOW: float = 0.05           # reduced rate for low income
TAX_THRESHOLD_HIGH: float = 300.0    # above this, higher rate applies
TAX_RATE_HIGH: float = 0.25          # higher rate for high income
WEALTH_TAX_RATE: float = 0.02        # annual wealth tax (applied per tick proportionally)

# ── Business ────────────────────────────────────────────────────────
BUSINESS_CAPITAL_REQUIREMENTS: dict = {
    "technology":  5000,
    "retail":      2000,
    "food":        1500,
    "services":    1000,
    "manufacturing": 8000,
    "entertainment": 3000,
}
BUSINESS_BASE_REVENUE: dict = {
    "technology":  200,
    "retail":      100,
    "food":        80,
    "services":    60,
    "manufacturing": 250,
    "entertainment": 120,
}
BUSINESS_OVERHEAD_RATE: float = 0.6   # fraction of revenue consumed by overhead
BUSINESS_FAILURE_THRESHOLD: float = 0.2  # if health drops below this, business closes

# ── Crime ───────────────────────────────────────────────────────────
CRIME_BASE_PROBABILITIES: dict = {
    "theft":       0.08,
    "burglary":    0.05,
    "assault":     0.03,
    "fraud":       0.04,
    "vandalism":   0.06,
}
CRIME_WEALTH_MODIFIER: float = -0.0002   # per unit wealth, reduces crime prob
CRIME_HAPPINESS_MODIFIER: float = 0.002  # per point happiness < 50 increases prob
CRIME_PUNISHMENT_SEVERITY: float = 0.5   # fraction of wealth lost on conviction

# ── Police / Law Enforcement ────────────────────────────────────────
POLICE_BUDGET_EFFECTIVENESS: float = 0.001  # per unit of police budget, reduces crime
POLICE_BASE_EFFECTIVENESS: float = 0.3       # baseline crime reduction factor

# ── Education & Skills ──────────────────────────────────────────────
SKILL_BASE_DECAY: float = 0.01     # daily skill decay without practice
SKILL_GAIN_PER_HOUR: float = 0.05  # skill gained per hour of study
SKILL_MAX: float = 100.0
EDUCATION_BUDGET_EFFECT: float = 0.0005  # per unit budget, extra skill gain multiplier

# ── Health ──────────────────────────────────────────────────────────
HEALTH_DECAY_BASE: float = 0.1      # daily health decay without healthcare
HEALTH_BUDGET_EFFECT: float = 0.02  # per unit healthcare budget reduces decay
HEALTH_RECOVERY_RATE: float = 0.5   # per tick recovery when budget is high enough
HEALTH_CRITICAL_THRESHOLD: float = 20.0  # below this, citizen may die

# ── Marriage ────────────────────────────────────────────────────────
MARRIAGE_BASE_PROBABILITY: float = 0.002  # per tick base chance for single adults
MARRIAGE_COMPATIBILITY_THRESHOLD: float = 0.6  # minimum score for marriage
DIVORCE_BASE_PROBABILITY: float = 0.001  # per tick base chance

# ── Travel ──────────────────────────────────────────────────────────
TRAVEL_COST_MULTIPLIER: float = 0.1    # fraction of wealth per day of travel
TRAVEL_HAPPINESS_BOOST: float = 5.0    # happiness gained per trip
TRAVEL_MIN_DURATION: int = 1           # minimum travel days

# ── Population ─────────────────────────────────────────────────────
DEATH_AGE_BASE: int = 70           # base age around which death probability rises
DEATH_AGE_MODIFIER: float = 0.02   # per year over 70, death prob increases
BIRTH_BASE_PROBABILITY: float = 0.001  # per tick per married couple
MAX_POPULATION: int = 100

# ── Starting stats for new citizens (born or immigrated) ────────────
NEW_CITIZEN_STATS: dict = {
    "age": 18,
    "happiness": 50.0,
    "wealth": 50.0,
    "health": 80.0,
    "social_score": 50.0,
}

# ── Disaster parameters ────────────────────────────────────────────
DISASTER_BASE_PROBABILITY: float = 0.02  # per tick chance any disaster fires
DISASTER_DAMAGE_RANGE: dict = {
    "fire":             {"wealth": (0.05, 0.30), "health": (0, 0.10)},
    "flood":            {"wealth": (0.10, 0.40), "health": (0, 0.15)},
    "recession":        {"wealth": (0.15, 0.35), "happiness": (0, 0.15)},
    "disease_outbreak": {"health": (0.10, 0.30), "happiness": (0.05, 0.20)},
}
DISASTER_AFFECTED_FRACTION: float = 0.3  # fraction of citizens affected by a disaster
