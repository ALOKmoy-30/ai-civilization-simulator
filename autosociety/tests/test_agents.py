"""
Pytest suite for agent systems with mocked LLM calls.
No real API calls are made during these tests.
"""

import pytest
from unittest.mock import patch, MagicMock

from crewai import LLM

from autosociety.backend.core.database import (
    init_db, get_session, create_citizen, CitizenCreate,
    get_citizen, get_or_create_world_state,
    DB_PATH, engine,
)
from autosociety.agents.tools.rag_search import create_rag_tool
from autosociety.agents.crews.citizen import build_citizen_agent, run_citizen_decision
from autosociety.agents.crews.government import GovernmentCrew


# ── Mock helpers ──────────────────────────────────────────────────────

def mock_llm():
    """Return a CrewAI LLM with a fake provider so no real API call is made."""
    return LLM(model="gemini/gemini-2.0-flash", api_key="mock-key")


def dummy_kickoff(text: str):
    """Helper to create a dummy Crew.kickoff result."""
    m = MagicMock()
    m.__str__.return_value = text
    return m


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db():
    """Fresh DB per test."""
    if DB_PATH.exists():
        try:
            engine.dispose()
            DB_PATH.unlink()
        except PermissionError:
            pass
    init_db()
    session = get_session()
    yield session
    session.close()
    engine.dispose()
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except PermissionError:
            pass


@pytest.fixture(scope="function")
def sample_citizen(db):
    """Insert a test citizen and return ID."""
    c = create_citizen(db, CitizenCreate(
        name="Test Citizen",
        age=35,
        job="Engineer",
        happiness=60.0,
        wealth=150.0,
        health=75.0,
        social_score=55.0,
    ))
    return c.id


# ── RAG Tool Tests ────────────────────────────────────────────────────

class TestRagTool:
    def test_create_tool(self):
        tool = create_rag_tool(citizen_id=42)
        assert tool.name == "MemorySearch"
        assert "memories" in tool.description.lower()

    def test_tool_no_memories(self):
        """When no memories exist, tool returns a helpful message."""
        tool = create_rag_tool(citizen_id=9999)
        result = tool._run("anything")
        assert "No relevant memories" in result


# ── Citizen Agent Tests ───────────────────────────────────────────────

class TestBuildCitizenAgent:
    def test_agent_created(self, sample_citizen):
        """Agent factory produces a correctly configured agent."""
        with patch("autosociety.agents.crews.citizen._build_llm") as mock_build:
            mock_build.return_value = mock_llm()
            agent = build_citizen_agent(sample_citizen)

        assert agent is not None
        assert "Test Citizen" in agent.role
        assert "Engineer" in agent.role
        assert agent.tools is not None
        assert any(t.name == "MemorySearch" for t in agent.tools)

    def test_agent_invalid_id(self, db):
        """Non-existent citizen raises ValueError."""
        db.close()
        with patch("autosociety.agents.crews.citizen._build_llm"):
            with pytest.raises(ValueError, match="not found"):
                build_citizen_agent(99999)

    def test_run_decision_writeback(self, sample_citizen):
        """Decision cycle writes effects back to citizen in DB."""
        with patch("autosociety.agents.crews.citizen._build_llm") as mock_build:
            mock_build.return_value = mock_llm()
            with patch("autosociety.agents.crews.citizen.Crew.kickoff") as mock_kickoff:
                mock_kickoff.return_value = dummy_kickoff(
                    "FINAL ACTION: Invest in local business. happiness: +3 wealth: +20"
                )
                result = run_citizen_decision(sample_citizen, "Test situation")

        assert result["citizen_id"] == sample_citizen
        assert "Test Citizen" in result["name"]

        # Verify DB was updated
        session = get_session()
        updated = get_citizen(session, sample_citizen)
        session.close()

        assert updated.happiness == 63.0  # 60 + 3
        assert updated.wealth == 170.0    # 150 + 20


# ── Government Crew Tests ─────────────────────────────────────────────

class TestGovernmentCrew:
    def test_crew_ministers_created(self):
        """GovernmentCrew creates all four ministers."""
        with patch("autosociety.agents.crews.government._build_llm") as mock_build:
            mock_build.return_value = mock_llm()
            crew = GovernmentCrew()

        assert "finance" in crew.ministers
        assert "police" in crew.ministers
        assert "education" in crew.ministers
        assert "health" in crew.ministers
        assert crew.ministers["finance"].role == "Finance Minister"

    def test_decide_policy(self, db):
        """Government policy cycle produces a structured, persisted decision."""
        get_or_create_world_state(db)
        db.close()

        with patch("autosociety.agents.crews.government._build_llm") as mock_build:
            mock_build.return_value = mock_llm()
            with patch("autosociety.agents.crews.government.Crew.kickoff") as mock_kickoff:
                mock_kickoff.return_value = dummy_kickoff(
                    "POLICY NAME: Community Development Act\n"
                    "DESCRIPTION: Fund local infrastructure\n"
                    "EFFECTS: economic_health=+5, avg_happiness=+3, political_stability=+2\n"
                    "DECISION: approved\n"
                    "ORDER: Implement immediately"
                )
                crew = GovernmentCrew()
                result = crew.decide_policy("The economy needs stimulus.")

        assert result["name"] == "Community Development Act"
        assert result["decision"] == "approved"
        assert "economic_health" in result["effects"]
        assert result["policy_id"] is not None

    def test_policy_world_state_updated(self, db):
        """Policy decision updates the world state."""
        get_or_create_world_state(db)
        db.close()

        with patch("autosociety.agents.crews.government._build_llm") as mock_build:
            mock_build.return_value = mock_llm()
            with patch("autosociety.agents.crews.government.Crew.kickoff") as mock_kickoff:
                mock_kickoff.return_value = dummy_kickoff(
                    "POLICY NAME: Economic Stimulus\n"
                    "DESCRIPTION: Tax cuts and spending\n"
                    "EFFECTS: economic_health=+5, avg_happiness=+3, political_stability=+2\n"
                    "DECISION: approved\n"
                    "ORDER: Implement"
                )
                crew = GovernmentCrew()
                result = crew.decide_policy("Stimulus needed")

        assert result["effects"]["economic_health"] == 5
        assert result["effects"]["avg_happiness"] == 3
        assert result["effects"]["political_stability"] == 2
