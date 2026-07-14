import os
from typing import Optional

from crewai import Agent, Task, Crew, Process
from crewai import LLM

from autosociety.backend.core.database import get_session, get_citizen, update_citizen, Citizen
from autosociety.agents.tools.rag_search import create_rag_tool


def _build_llm():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY env var not set")
    return LLM(
        model="gemini/gemini-2.0-flash",
        api_key=api_key,
        temperature=0.7,
    )


def build_citizen_agent(citizen_id: int) -> Agent:
    """Load a citizen from SQLite and construct a CrewAI Agent with RAG tool."""
    session = get_session()
    citizen = get_citizen(session, citizen_id)
    session.close()

    if not citizen:
        raise ValueError(f"Citizen {citizen_id} not found in database")

    mood = "cheerful" if citizen.happiness > 70 else "content" if citizen.happiness > 40 else "gloomy"
    energy = "energetic" if citizen.health > 70 else "moderate" if citizen.health > 40 else "tired"
    social = "outgoing" if citizen.social_score > 60 else "reserved"
    wealth_desc = "comfortable" if citizen.wealth > 200 else "modest" if citizen.wealth > 100 else "struggling"

    agent = Agent(
        role=f"{citizen.name}, {citizen.job}",
        goal=(
            f"Live your life as {citizen.name}, a {citizen.age}-year-old {citizen.job}. "
            f"You are currently {mood} and feeling {energy}. "
            f"Your finances are {wealth_desc} (${citizen.wealth:.0f}). "
            f"You are {social} by nature. "
            f"Respond to situations in character, drawing on your personal memories and circumstances."
        ),
        backstory=(
            f"You are {citizen.name}, age {citizen.age}. You work as a {citizen.job}. "
            f"Your happiness level is {citizen.happiness:.0f}/100, health is {citizen.health:.0f}/100, "
            f"wealth is ${citizen.wealth:.0f}, and social score is {citizen.social_score:.0f}/100. "
            f"Think carefully about decisions based on these personal circumstances."
        ),
        verbose=False,
        allow_delegation=False,
        llm=_build_llm(),
        tools=[create_rag_tool(citizen_id)],
    )

    return agent


def run_citizen_decision(citizen_id: int, situation: str) -> dict:
    """Run one reasoning task for a citizen and persist the decision."""
    session = get_session()
    citizen = get_citizen(session, citizen_id)
    if not citizen:
        session.close()
        raise ValueError(f"Citizen {citizen_id} not found")

    agent = build_citizen_agent(citizen_id)

    task = Task(
        description=(
            f"You observe: {situation}\n\n"
            f"As {citizen.name}, decide how to react. "
            f"Search your memories for relevant past experiences, then make your decision. "
            f"Explain your reasoning and state your final action clearly."
        ),
        expected_output=(
            "A brief paragraph with your reasoning, followed by "
            "'FINAL ACTION: <what you decide to do>'"
        ),
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=False,
        process=Process.sequential,
    )

    result = crew.kickoff()
    decision_text = str(result)

    # Persist decision effects on the citizen
    happiness_delta = _extract_delta(decision_text, "happiness", default=-2)
    wealth_delta = _extract_delta(decision_text, "wealth", default=-5)

    update_citizen(session, citizen_id, {
        "happiness": max(0, min(100, citizen.happiness + happiness_delta)),
        "wealth": max(0, citizen.wealth + wealth_delta),
    })
    session.close()

    return {
        "citizen_id": citizen_id,
        "name": citizen.name,
        "situation": situation,
        "decision": decision_text,
        "effects": {"happiness_delta": happiness_delta, "wealth_delta": wealth_delta},
    }


def _extract_delta(text: str, key: str, default: int = 0) -> int:
    import re
    pattern = rf"{key}\s*[:=]?\s*([+-]?\d+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return default
