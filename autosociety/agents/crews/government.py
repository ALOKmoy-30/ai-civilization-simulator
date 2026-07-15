import os
from typing import Any, Dict

from crewai import Agent, Task, Crew, Process, LLM

from autosociety.backend.core.database import (
    get_session, get_or_create_world_state, update_world_state,
    create_policy, PolicyCreate,
)


def _build_llm(temperature: float = 0.4):
    """Build a CrewAI LLM, routing through 9Router proxy if GEMINI_API_BASE is set."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY env var not set")
    api_base = os.getenv("GEMINI_API_BASE")  # e.g. http://localhost:20128/v1

    if api_base:
        # Route through 9Router OpenAI-compatible proxy via LiteLLM
        return LLM(
            model="openai/gemini-2.0-flash",
            api_key=api_key,
            base_url=api_base,
            temperature=temperature,
        )
    else:
        # Direct Gemini access (no proxy)
        return LLM(
            model="gemini/gemini-2.0-flash",
            api_key=api_key,
            temperature=temperature,
        )


MINISTER_ROLES = {
    "finance": {
        "role": "Finance Minister",
        "goal": "Manage the society's economy — propose tax rates, budget allocations, and economic policies.",
        "backstory": "You are the Finance Minister, responsible for the economic health of the society. "
                     "You balance budgets, propose taxes, and fund government programs.",
    },
    "police": {
        "role": "Police Chief",
        "goal": "Maintain public order and safety — propose crime prevention and law enforcement policies.",
        "backstory": "You are the Police Chief, responsible for law and order. "
                     "You propose security policies and manage public safety resources.",
    },
    "education": {
        "role": "Education Minister",
        "goal": "Develop the society's human capital — propose education funding and skill development programs.",
        "backstory": "You are the Education Minister, responsible for schools and skill development. "
                     "You propose policies that improve citizen capabilities.",
    },
    "health": {
        "role": "Health Minister",
        "goal": "Protect public health — propose healthcare policies, sanitation, and wellness programs.",
        "backstory": "You are the Health Minister, responsible for the well-being of all citizens. "
                     "You propose health policies and manage medical resources.",
    },
}


class GovernmentCrew:
    """Assembles the Government ministers and runs policy decisions."""

    def __init__(self):
        self.llm = _build_llm()
        self.ministers: Dict[str, Agent] = {}
        self._build_ministers()

    def _build_ministers(self):
        for key, cfg in MINISTER_ROLES.items():
            self.ministers[key] = Agent(
                role=cfg["role"],
                goal=cfg["goal"],
                backstory=cfg["backstory"],
                verbose=False,
                allow_delegation=False,
                llm=self.llm,
            )

    def _build_policy_coordinator(self) -> Agent:
        return Agent(
            role="Policy Coordinator",
            goal=(
                "Review all ministerial proposals, resolve conflicts, "
                "and produce a single unified policy recommendation."
            ),
            backstory=(
                "You are the Policy Coordinator. Your job is to synthesize "
                "proposals from all ministers into a coherent, non-contradictory "
                "policy package for the Governor's final decision."
            ),
            verbose=False,
            allow_delegation=False,
            llm=self.llm,
        )

    def _build_decision_aggregator(self) -> Agent:
        return Agent(
            role="Governor",
            goal=(
                "Review the Policy Coordinator's unified recommendation and "
                "issue a final binding policy decision for the society."
            ),
            backstory=(
                "You are the Governor, the final decision-maker. "
                "You weigh trade-offs, consider the common good, and issue decisive policy orders."
            ),
            verbose=False,
            allow_delegation=False,
            llm=self.llm,
        )

    def decide_policy(self, situation: str) -> Dict[str, Any]:
        """Run a full government policy cycle and return a structured decision."""
        # Load current world state
        session = get_session()
        world = get_or_create_world_state(session)
        session.close()

        context = (
            f"Society situation: {situation}\n"
            f"Current world state: day {world.simulation_day}, "
            f"avg happiness {world.avg_happiness:.1f}, "
            f"political stability {world.political_stability:.1f}, "
            f"economic health {world.economic_health:.1f}."
        )

        tasks = []

        # Phase 1: each minister proposes
        for key, agent in self.ministers.items():
            tasks.append(Task(
                description=(
                    f"{context}\n\n"
                    f"As {agent.role}, propose exactly ONE specific policy to address this situation. "
                    f"State your proposal clearly, explain why it helps, and list expected effects "
                    f"on happiness, wealth, stability, or health."
                ),
                expected_output=(
                    "A short proposal with the policy name, rationale, and expected numeric effects."
                ),
                agent=agent,
            ))

        # Phase 2: Policy Coordinator synthesizes
        coordinator = self._build_policy_coordinator()
        tasks.append(Task(
            description=(
                f"{context}\n\n"
                f"Review the ministerial proposals above. Resolve any contradictions and "
                f"synthesize them into ONE unified policy package. "
                f"Name the package, describe its provisions, and estimate overall effects."
            ),
            expected_output=(
                "Unified policy package name, provisions, and estimated net effects on "
                "economic_health, avg_happiness, and political_stability (each -10 to +10)."
            ),
            agent=coordinator,
        ))

        # Phase 3: Governor final decision
        governor = self._build_decision_aggregator()
        tasks.append(Task(
            description=(
                f"{context}\n\n"
                f"Review the Policy Coordinator's recommendation below. "
                f"Issue your final binding decision. "
                f"Output in this exact format:\n"
                f"POLICY NAME: <name>\n"
                f"DESCRIPTION: <description>\n"
                f"EFFECTS: economic_health=X, avg_happiness=Y, political_stability=Z\n"
                f"DECISION: <approved or rejected or modified>\n"
                f"ORDER: <final orders to implement>"
            ),
            expected_output=(
                "A structured policy decision with name, description, numeric effects, and approval status."
            ),
            agent=governor,
        ))

        crew = Crew(
            agents=list(self.ministers.values()) + [coordinator, governor],
            tasks=tasks,
            verbose=False,
            process=Process.sequential,
        )

        result = crew.kickoff()
        decision_text = str(result)

        # Parse structured output and persist
        policy_name = _extract_field(decision_text, "POLICY NAME", "Unnamed Policy")
        description = _extract_field(decision_text, "DESCRIPTION", decision_text[:200])
        effects_raw = _extract_field(decision_text, "EFFECTS", "")
        decision_status = _extract_field(decision_text, "DECISION", "approved")

        # Parse numeric effects
        effects = _parse_effects(effects_raw)

        # Update world state
        session = get_session()
        world = get_or_create_world_state(session)
        new_happiness = max(0, min(100, world.avg_happiness + effects.get("avg_happiness", 0)))
        new_stability = max(0, min(100, world.political_stability + effects.get("political_stability", 0)))
        new_economic = max(0, min(100, world.economic_health + effects.get("economic_health", 0)))

        update_world_state(session, {
            "avg_happiness": new_happiness,
            "political_stability": new_stability,
            "economic_health": new_economic,
            "simulation_day": world.simulation_day + 1,
        })

        # Persist as a Policy record
        policy = create_policy(session, PolicyCreate(
            name=policy_name,
            description=description,
            effects=str(effects),
        ))
        session.close()

        return {
            "policy_id": policy.id,
            "name": policy_name,
            "description": description,
            "effects": effects,
            "decision": decision_status,
            "raw_output": decision_text,
        }


def _extract_field(text: str, field: str, default: str = "") -> str:
    """Extract a labeled field from structured output."""
    import re
    pattern = rf"{re.escape(field)}:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else default


def _parse_effects(raw: str) -> Dict[str, int]:
    """Parse 'economic_health=X, avg_happiness=Y, ...' into a dict."""
    import re
    effects = {}
    for match in re.finditer(r"(\w+)\s*=\s*([+-]?\d+)", raw):
        effects[match.group(1)] = int(match.group(2))
    return effects
