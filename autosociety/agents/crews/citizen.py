from typing import Optional

from crewai import Agent, Task, Crew, Process

from autosociety.backend.core.database import get_session, get_citizen, update_citizen, Citizen
from autosociety.agents.tools.rag_search import create_rag_tool
from autosociety.agents.llm_config import get_citizen_llm


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
        llm=get_citizen_llm(),
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
    readable_action = _clean_decision_output(decision_text)

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
        "readable_action": readable_action,
        "effects": {"happiness_delta": happiness_delta, "wealth_delta": wealth_delta},
    }


def _clean_decision_output(raw_text: str) -> str:
    """Extract human-readable action and reasoning from raw LLM output (JSON or markdown)."""
    import re
    import json
    text = raw_text.strip()

    # Try to extract JSON from ```json ... ``` or raw {...} block
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not json_match and text.startswith("{") and text.endswith("}"):
        json_match = re.match(r"(\{.*\})", text, re.DOTALL)

    if json_match:
        try:
            data = json.loads(json_match.group(1))
            action = data.get("final_action") or data.get("action") or data.get("decision")
            reasoning = data.get("reasoning") or data.get("thought") or data.get("explanation")
            if action:
                if reasoning and len(str(reasoning)) > 10:
                    return f"{action} (Reasoning: {reasoning})"
                return str(action)
        except Exception:
            pass

    # Look for 'FINAL ACTION:' or 'Action:'
    action_match = re.search(r"(?:FINAL\s+ACTION|ACTION|DECISION)\s*[:=]\s*(.+?)(?:\n\n|$)", text, re.IGNORECASE | re.DOTALL)
    if action_match:
        action_clean = action_match.group(1).strip()
        action_clean = re.sub(r"```.*", "", action_clean, flags=re.DOTALL).strip()
        if action_clean:
            return action_clean

    # Fallback: clean up raw markdown code blocks
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    cleaned = re.sub(r"\n+", " ", cleaned)
    return cleaned[:300] if cleaned else "No explicit action recorded."


def _extract_delta(text: str, key: str, default: int = 0) -> int:
    import re
    pattern = rf"{key}\s*[:=]?\s*([+-]?\d+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return default
