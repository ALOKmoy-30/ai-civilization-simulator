# AutoSociety — 5-Phase Coding Agent Prompts

**How to use this:** Paste one phase into your coding agent (Claude Code, Aider, etc.) at a time. Don't move to the next phase until the agent has checked off every box in that phase's Definition of Done. Each prompt is fully self-contained — the agent doesn't need to see the diagram or this intro, just the code block.

Build order: Data & Memory → Agent Systems & RAG → World Rules Engine & Scheduler → FastAPI Backend → Streamlit Dashboard. This matches your own roadmap (DB first, then RAG, then a single test agent, then API, then UI), with one addition: Phase 3 defines the actual economy/behavior rules and a tick-batching scheduler before the API wires everything into a live loop — without it, agents would be reasoning against wage/tax/business numbers that don't exist yet.

---

## Phase 1: Data & Memory Layer (SQLite + ChromaDB)

```
ROLE: You are building "AutoSociety," a Python-based multi-agent society simulator for 30-40 AI citizens. You are currently working ONLY on Phase 1 of 5: the Data & Memory Layer.

SYSTEM CONTEXT:
This phase builds the foundational persistence layer only. There is no FastAPI app, no CrewAI agent, and no Streamlit UI yet — those come in later phases. Everything you build here must run and be testable as standalone Python, with no dependency on code that doesn't exist yet.

The project root is `autosociety/`. Two datastores are used:
- SQLite (via SQLAlchemy ORM) for structured state: Citizens, World State, Policies, Businesses, Events, Simulation Logs.
- ChromaDB (local, persistent client) for agent memories and RAG knowledge, stored in `data_storage/chroma_db/`.

FILE STRUCTURE DIRECTIVES:
Create or modify exactly these files:
- `autosociety/requirements.txt` — add: sqlalchemy, chromadb, python-dotenv, pydantic, faker, pytest
- `autosociety/.env.example` — placeholder for GEMINI_API_KEY (do not add real keys)
- `autosociety/backend/__init__.py` — empty
- `autosociety/backend/core/__init__.py` — empty
- `autosociety/backend/core/database.py` — SQLAlchemy models (Citizen, WorldState, Policy, Business, Event, SimulationLog) + a DB session/engine setup pointed at `data_storage/autosociety.db` + CRUD helper functions (create_citizen, get_citizen, list_citizens, update_citizen, etc.)
- `autosociety/backend/core/vector_store.py` — a ChromaDB PersistentClient pointed at `data_storage/chroma_db/`, with a single collection for agent memories, plus `add_memory(citizen_id, text, metadata)` and `search_memory(citizen_id, query, k=5)` functions
- `autosociety/scripts/seed_dummy_citizens.py` — a script that uses Faker to generate and insert 30 dummy citizens with realistic names, ages, jobs, and starting stats
- `autosociety/tests/test_database.py` — pytest suite for database.py
- `autosociety/tests/test_vector_store.py` — pytest suite for vector_store.py

STRICT CONSTRAINTS:
- Do NOT write any FastAPI, CrewAI, LangChain, or Streamlit code in this phase.
- Use SQLAlchemy ORM, not raw sqlite3 strings.
- Define Pydantic schemas alongside the ORM models for input validation (e.g. CitizenCreate, CitizenRead) — keep them simple, no over-engineering.
- All file paths must be relative/configurable (read the `data_storage/` path from a constant or .env, never hardcode an absolute path).
- `data_storage/` and its contents must be created automatically by the code on first run, not manually committed.
- Do not call the Gemini API anywhere in this phase.
- Keep it simple: prefer straightforward functions over unnecessary abstraction layers or design patterns.

DEFINITION OF DONE — verify all of these before considering Phase 1 complete:
- [ ] Running `python -m scripts.seed_dummy_citizens` creates `data_storage/autosociety.db` and inserts exactly 30 citizens with no errors.
- [ ] A follow-up read (e.g. `list_citizens()`) returns all 30 citizens with correctly populated fields.
- [ ] `add_memory()` followed by `search_memory()` on the same citizen_id returns the injected memory text as the top result.
- [ ] `pytest autosociety/tests/` passes with zero failures.

Report back the exact commands you ran and their output before moving to the next phase.
```

---

## Phase 2: Agent Systems & RAG Flow (CrewAI + Gemini)

```
ROLE: You are continuing work on "AutoSociety." Phase 1 (SQLite + ChromaDB data layer) is complete and tested. You are now working ONLY on Phase 2 of 5: Agent Systems & RAG Flow.

SYSTEM CONTEXT:
This phase builds the CrewAI agent logic: individual Citizen agents and a Government crew (Finance Minister, Police Chief, Education Minister, Health Minister, plus a Policy Coordinator and Decision Aggregator that roll up into a Governor decision). Agents use Gemini as their LLM and a custom RAG tool to retrieve relevant memories from the Phase 1 ChromaDB store before reasoning. Agent decisions are written back to SQLite using the Phase 1 database module — do not duplicate or bypass that data-access layer.

Still no FastAPI app and no Streamlit UI in this phase. Test everything via standalone scripts.

NOTE: CrewAI's Gemini/LiteLLM provider syntax changes between versions. Check the currently installed CrewAI version's docs for the correct model string and provider config rather than assuming a specific format.

FILE STRUCTURE DIRECTIVES:
Create or modify exactly these files:
- `autosociety/requirements.txt` — add: crewai, langchain, and whichever Gemini provider package CrewAI's current docs specify
- `autosociety/agents/__init__.py` — empty
- `autosociety/agents/tools/__init__.py` — empty
- `autosociety/agents/tools/rag_search.py` — a CrewAI/LangChain custom Tool that wraps `backend/core/vector_store.py`'s `search_memory()` function so an agent can call it during reasoning
- `autosociety/agents/crews/__init__.py` — empty
- `autosociety/agents/crews/citizen.py` — a factory function `build_citizen_agent(citizen_id)` that loads that citizen's row from SQLite, constructs a CrewAI Agent with a personality/goal derived from their stats, gives it the RAG tool, and a function `run_citizen_decision(citizen_id, situation)` that runs one reasoning task and writes the resulting action back to the citizen's row via the Phase 1 database module
- `autosociety/agents/crews/government.py` — a `GovernmentCrew` class assembling the Finance Minister, Police Chief, Education Minister, and Health Minister agents plus a Policy Coordinator/Decision Aggregator step that produces a single policy decision object
- `autosociety/scripts/test_single_citizen.py` — a manual test script that builds ONE citizen agent, gives it a sample situation, and prints its decision
- `autosociety/tests/test_agents.py` — pytest suite that MOCKS the Gemini API call (do not make real paid API calls in the test suite) and verifies the tool-calling and DB-writeback logic

STRICT CONSTRAINTS:
- Build and manually verify ONE citizen agent end-to-end before writing any code intended to scale to 30-40 agents.
- The RAG tool must query the SAME ChromaDB collection created in Phase 1 — do not initialize a second/parallel vector store.
- All agent decisions must be persisted through the existing `backend/core/database.py` functions, not new ad-hoc DB code.
- No FastAPI, WebSocket, or Streamlit code.
- Do not run CrewAI kickoffs inside an async event loop yet — these are synchronous test scripts; async wiring happens in Phase 3.
- Keep the Government crew and Citizen agents in separate modules as specified — do not merge them into one file.

DEFINITION OF DONE — verify all of these before considering Phase 2 complete:
- [ ] `python -m scripts.test_single_citizen` runs one citizen agent through a full observe → RAG search → Gemini reasoning → decision cycle and prints a coherent decision.
- [ ] That decision is visible when you re-read the citizen's row from SQLite (state actually changed).
- [ ] `GovernmentCrew().decide_policy(...)` runs independently and returns a structured policy decision (not just raw text).
- [ ] `pytest autosociety/tests/test_agents.py` passes using mocked LLM calls, with zero real API calls made during the test run.

Report back the exact commands you ran and their output before moving to the next phase.
```

---

## Phase 3: World Rules Engine, Scheduler & Historical Metrics

*Do this after Phase 2 and before Phase 4 — the FastAPI tick loop in Phase 4 depends on the scheduler and rule functions built here.*

```
ROLE: You are continuing work on "AutoSociety." Phases 1 (data layer) and 2 (agent systems) are complete. You are now working ONLY on Phase 3 of 5: the World Rules Engine, Action Scheduler, and Historical Metrics logging.

SYSTEM CONTEXT:
The goal is 40 citizens simulating months of daily life — jobs, taxes, skills, marriage, businesses, voting, crime, travel — under a Government AI that sets policy and responds to disasters, so students can later chart how the society evolved. Two problems must be solved before that's viable:
1. LLM agents are bad at consistent arithmetic across hundreds of ticks. The LLM should decide INTENT and JUDGMENT (e.g. "citizen X wants to open a bakery," "citizen Y is tempted to steal") — deterministic Python functions should decide the MATH (wage owed, tax owed, business revenue, crime success probability, disaster damage). Never let the LLM freehand a specific number that affects world state.
2. Running full LLM reasoning for all 40 citizens on every tick is too slow/expensive for a months-long simulation. Use a rotating scheduler where ~40-50% of citizens get a full reasoning cycle per tick (not random selection — a fixed rotation so coverage is guaranteed, not left to chance). At that rate, every citizen should get a full reasoning cycle at least once every 2-3 ticks.

1 tick = 1 simulated day, and 30 ticks = 1 simulated month (literal). This is the unit the historical metrics below should be logged and later aggregated by.


FILE STRUCTURE DIRECTIVES:
Create or modify exactly these files:
- `autosociety/backend/core/world_rules.py` — deterministic functions: `calculate_tax(income, rate)`, `calculate_wage(job, skill_level)`, `business_outcome(capital, business_type, local_demand)`, `skill_progression(current_level, hours_invested)`, `marriage_compatibility(citizen_a, citizen_b)`, `crime_outcome(citizen, crime_type, law_enforcement_budget)`, `travel_effects(citizen, destination)`
- `autosociety/backend/core/config/world_config.py` (or `.yaml`) — all tunable parameters as named constants/config, NOT magic numbers scattered in code: job wage table, base tax rate, business capital requirements, crime base probabilities, disaster probabilities, `CITIZEN_REASONING_RATE = 0.45` (45% of citizens reasoned per tick), `TICKS_PER_MONTH = 30`. Students should be able to tweak these for experiments without touching logic code.
- `autosociety/backend/core/policies.py` — the set of policies the Government crew can enact (tax rate change, budget reallocation across health/education/police, emergency relief) and a function applying each policy's effect to `world_config` / world state
- `autosociety/backend/core/disasters.py` — disaster types (fire, flood, recession, disease outbreak) with trigger probability per tick and a function computing their effect on affected citizens and the economy when one fires
- `autosociety/backend/core/scheduler.py` — `ActionScheduler` class: each tick, selects a rotating (fixed round-robin, not random) subset of citizens equal to `CITIZEN_REASONING_RATE` of the population (roughly 16-20 of ~40 citizens) to run a full CrewAI reasoning cycle; all other citizens get a lightweight deterministic stat update (income accrual, skill decay/growth, aging) with no LLM call. Must guarantee every citizen gets at least one full reasoning cycle within any rolling 3-tick window.
- `autosociety/backend/core/metrics.py` — extends analytics to write an append-only historical snapshot every tick (population, GDP, employment rate, crime rate, average happiness, tax revenue, active businesses) to a dedicated table, plus a `export_metrics_csv()` function for students to pull the full time series
- `autosociety/tests/test_world_rules.py` — unit tests with deterministic expected outputs for each rule function
- `autosociety/tests/test_scheduler.py` — verifies the rolling-window guarantee

STRICT CONSTRAINTS:
- LLM calls only happen for judgment/decision-making (should I, who should I, do I). All resulting numbers (money, probabilities, damage) come from `world_rules.py`, never from LLM text output.
- All tunable parameters live in `world_config`, not hardcoded inline.
- The scheduler's rolling-window guarantee is non-negotiable — write a test that runs 10+ simulated ticks with a mocked LLM and asserts no citizen was skipped for more than 3 consecutive ticks.
- Historical metrics are append-only — pausing, resuming, or restarting the server must never overwrite prior history.
- Do not write any FastAPI or Streamlit code yet — these are still standalone modules and scripts, wired into the API in Phase 3.

DEFINITION OF DONE — verify all of these before considering Phase 3 complete:
- [ ] Each function in `world_rules.py` has a unit test with a known input/output pair, and all pass.
- [ ] A scripted 10-tick dry run (mocked LLM) confirms via `test_scheduler.py` that every citizen received at least one full reasoning cycle, and no citizen went more than 3 ticks without one.
- [ ] Manually triggering a disaster in a test script visibly changes affected citizens' stats and is recorded in the event log.
- [ ] After a scripted 30-tick dry run (= 1 simulated month), `export_metrics_csv()` produces a CSV with 30 rows of believable, non-static values for population/GDP/crime rate that could be charted directly in Excel or Plotly.

Report back the exact commands you ran and their output before moving to Phase 4.
```

---

## Phase 4: FastAPI Backend (Engine & Endpoints)

```
ROLE: You are continuing work on "AutoSociety." Phases 1 (data layer), 2 (agent systems), and 3 (world rules & scheduler) are complete and tested. You are now working ONLY on Phase 4 of 5: the FastAPI Backend.

SYSTEM CONTEXT:
This phase wraps the existing data layer, agent layer, and Phase 3 world-rules/scheduler in a FastAPI application with a background Simulation Clock (1 tick = 1 simulated day) that runs as an asyncio background task, plus REST endpoints that the Streamlit frontend (Phase 4) will poll. Because CrewAI agent calls are synchronous/blocking, they must never run directly inside the asyncio event loop — offload them to a thread pool so the API stays responsive.

FILE STRUCTURE DIRECTIVES:
Create or modify exactly these files:
- `autosociety/requirements.txt` — add: fastapi, uvicorn[standard]
- `autosociety/backend/main.py` — FastAPI app instance, includes the routers below, defines app startup/shutdown events
- `autosociety/backend/routers/__init__.py` — empty
- `autosociety/backend/routers/simulation.py` — endpoints: `POST /start-simulation`, `POST /pause-simulation`, `POST /reset-simulation`, `GET /get-world-state`
- `autosociety/backend/routers/queries.py` — endpoints: `GET /get-citizens`, `GET /get-citizens/{citizen_id}`, `GET /get-policies`, `GET /get-events`, `GET /get-analytics`, `GET /get-reports`
- `autosociety/backend/core/engine.py` — `SimulationEngine` class: holds tick count and running/paused state, an asyncio background loop that on each tick (a) advances world state, (b) calls the Phase 3 `ActionScheduler` to get this tick's ~45% citizen subset and runs their reasoning via `asyncio.to_thread`, applying lightweight updates to everyone else, (c) periodically triggers the Government crew and disaster checks, (d) logs events and appends a metrics snapshot via `metrics.py`, using `TICKS_PER_MONTH = 30` as the unit reflected in analytics
- `autosociety/tests/test_api.py` — pytest suite using FastAPI's `TestClient`

STRICT CONSTRAINTS:
- All CrewAI/agent calls inside the tick loop MUST be wrapped in `asyncio.to_thread(...)` (or an executor) — never call a blocking CrewAI kickoff directly on the event loop.
- All endpoint request/response bodies must use Pydantic models, not raw dicts.
- The simulation must be pausable and resumable without restarting the server or losing state.
- Do not write any Streamlit code in this phase.
- WebSocket endpoints (`/ws/world-updates`, etc.) are optional/stretch for this phase — the primary integration path for Phase 4 is plain REST polling, matching the existing build plan. Only add WebSockets if REST is fully working first.
- Reuse the Phase 1 database/vector-store modules and Phase 2 agent modules as-is — do not re-implement their logic inside `engine.py`.

DEFINITION OF DONE — verify all of these before considering Phase 3 complete:
- [ ] `uvicorn backend.main:app --reload` boots with no errors.
- [ ] `GET /get-citizens` returns the 30 seeded citizens as JSON.
- [ ] `POST /start-simulation` starts the background loop, and polling `GET /get-world-state` a few seconds apart shows the tick count increasing without the request ever hanging.
- [ ] `POST /pause-simulation` stops tick progression, verified by two consecutive `GET /get-world-state` calls returning the same tick count.
- [ ] `pytest autosociety/tests/test_api.py` passes with zero failures.

Report back the exact commands you ran and their output before moving to the next phase.
```

---

## Phase 5: Streamlit Dashboard (UI & Polling)

```
ROLE: You are continuing work on "AutoSociety." Phases 1-4 (data layer, agents, world rules, FastAPI backend) are complete, tested, and the server can be started with `uvicorn backend.main:app`. You are now working ONLY on Phase 5 of 5: the Streamlit Dashboard.

SYSTEM CONTEXT:
This phase builds the Streamlit UI that polls the FastAPI backend from Phase 3 and renders it as a live dashboard. The frontend is a pure consumer of the REST API — it must never touch SQLite or ChromaDB directly. Also build a single master script that boots both servers together.

FILE STRUCTURE DIRECTIVES:
Create or modify exactly these files:
- `autosociety/requirements.txt` — add: streamlit, plotly, requests
- `autosociety/frontend/app.py` — main entry point: sidebar navigation, Simulation Controls panel (start/pause/reset buttons calling the FastAPI endpoints), Live Analytics panel (GDP, population, happiness index, etc. via Plotly charts), and a polling loop using `st.session_state` + a fixed interval (2-3 seconds)
- `autosociety/frontend/pages/1_Analytics.py` — deeper analytics charts (economy trends, crime rate, employment)
- `autosociety/frontend/pages/2_Government.py` — Government Panel: current policies, budget allocation, recent decisions
- `autosociety/frontend/pages/3_Citizens.py` — Society Explorer: searchable/filterable table of all citizens with their current stats and relationships
- `autosociety/frontend/components/__init__.py` — empty
- `autosociety/frontend/components/charts.py` — reusable Plotly chart-building functions imported by the pages above
- `autosociety/run_sim.py` — a script that launches `uvicorn` and `streamlit run` as subprocesses so the whole app starts with one command

STRICT CONSTRAINTS:
- No direct database or ChromaDB imports anywhere under `frontend/` — all data comes from HTTP calls to the FastAPI backend using `requests`.
- Poll at a fixed, reasonable interval (2-3 seconds) — do not hammer the API on every Streamlit rerun with no throttling.
- No CrewAI or LLM calls originate from the frontend.
- Handle the case where the FastAPI backend isn't running yet (show a friendly "backend not reachable" message instead of crashing).
- Keep chart-building logic in `components/charts.py`, not inlined repeatedly across pages.

DEFINITION OF DONE — verify all of these before considering Phase 4 (and the project) complete:
- [ ] `python run_sim.py` boots both the FastAPI backend and the Streamlit frontend with one command.
- [ ] The Simulation Controls panel's Start button actually starts the tick loop — verified by the Live Analytics panel's tick/day counter increasing on screen without a manual page refresh.
- [ ] The Society Explorer page displays all 30+ citizens with live stats pulled from `/get-citizens`.
- [ ] The Government Panel displays at least one policy decision pulled from `/get-policies`.
- [ ] If the backend is stopped, the Streamlit app shows a graceful error instead of an unhandled exception.

This is the final phase — once verified, the full AutoSociety pipeline (data → agents → API → dashboard) should be running end-to-end.
```











To adapt this comprehensive execution plan for your coding agent while seamlessly swapping in **Kiro AI** (and your robust **Gemini** simulation stack) without breaking the core logic, we need to inject specialized model handling and token compression directly into the prompts.

Here are the compressed, production-ready prompts for **Phases 2 through 5**, updated to ensure absolute architectural integrity while using your specific 9Router setup.

---

### **Phase 2: Agent Systems & RAG Flow (CrewAI + Gemini/Kiro)**

```
ROLE: Senior Agent Engineer. Build Phase 2 of 5: Agent Systems & RAG Flow for "AutoSociety." 

SYSTEM CONTEXT:
Build individual Citizen agents and a Government crew (Finance, Police, Education, Health, Policy Coordinator, Aggregator, Governor). Use the `claude-3-5-sonnet-20241022` 9Router combo for coding reasoning tasks, and the `gemini` combo (Flash Lite/Flash) for simulation agents. Implement a custom RAG tool wrapping Phase 1's `backend/core/vector_store.py` -> `search_memory()`. Write decisions back to SQLite using existing Phase 1 DAL functions. 

FILE STRUCTURE DIRECTIVES:
- `autosociety/requirements.txt` — Add: crewai, langchain
- `autosociety/agents/__init__.py`, `agents/tools/__init__.py`, `agents/crews/__init__.py` — [Empty]
- `autosociety/agents/tools/rag_search.py` — Custom CrewAI/LangChain Tool wrapping `search_memory()`.
- `autosociety/agents/crews/citizen.py` — `build_citizen_agent(citizen_id)` and `run_citizen_decision(citizen_id, situation)`.
- `autosociety/agents/crews/government.py` — `GovernmentCrew` class executing specialized agents and generating a single structured policy object.
- `autosociety/scripts/test_single_citizen.py` — Test script booting ONE citizen agent with a mock scenario.
- `autosociety/tests/test_agents.py` — Pytest suite using `unittest.mock` to mock LLM calls.

STRICT CONSTRAINTS:
1. Verify ONE citizen agent end-to-end before scaling.
2. Query the exact same ChromaDB collection from Phase 1.
3. Hook LLM configurations to point to local 9Router base URL (`http://127.0.0.1:20128/v1`). Set citizen agents to use the `gemini` string.
4. Run CrewAI kickoffs synchronously; no async wiring yet. Keep modules strictly isolated.

DEFINITION OF DONE:
- `python -m scripts.test_single_citizen` runs observe -> RAG -> Gemini loop cleanly.
- Decision state changes are verified via SQLite re-read.
- `pytest autosociety/tests/test_agents.py` passes with zero real API calls.

```

---

### **Phase 3: World Rules Engine, Scheduler & Metrics**

```
ROLE: Systems Architect. Build Phase 3 of 5: World Rules, Scheduler, and Metrics for "AutoSociety."

SYSTEM CONTEXT:
Solve calculation drift and execution speed for 40 citizens over months of ticks (1 tick = 1 day, 30 ticks = 1 month). The LLM determines INTENT and JUDGMENT; pure Python functions in `world_rules.py` handle the MATH. Use a fixed round-robin scheduler routing a rotating 45% subset (`CITIZEN_REASONING_RATE = 0.45`) through full LLM reasoning each tick. The rest receive lightweight deterministic parameter ticks. Every agent must reason at least once every 3 ticks.

FILE STRUCTURE DIRECTIVES:
- `autosociety/backend/core/config/world_config.py` — Configuration file housing all named constants (wages, tax rates, capital limits, disaster odds, rate targets). No magic numbers inline.
- `autosociety/backend/core/world_rules.py` — Deterministic functions: `calculate_tax`, `calculate_wage`, `business_outcome`, `skill_progression`, `marriage_compatibility`, `crime_outcome`, `travel_effects`.
- `autosociety/backend/core/policies.py` — Government policy definitions and functions modifying `world_config` dynamically.
- `autosociety/backend/core/disasters.py` — Event triggers (fire, recession, disease) applying damage matrix to stats.
- `autosociety/backend/core/scheduler.py` — `ActionScheduler` class managing the fixed rolling round-robin queue.
- `autosociety/backend/core/metrics.py` — Append-only historical tick engine saving snapshots to database, plus `export_metrics_csv()`.
- `autosociety/tests/test_world_rules.py` & `test_scheduler.py` — Full verification suites.

STRICT CONSTRAINTS:
1. All mathematical updates must be deterministic; the LLM must never output exact state integers.
2. The scheduler rolling-window guarantee is non-negotiable.
3. Historical metrics table must be explicitly append-only; server restarts must not clear logs.
4. Create a comprehensive `.gitignore` explicitly blocking `venv/`, `__pycache__/`, and `data_storage/` to prevent token bloat during agent terminal operations.

DEFINITION OF DONE:
- All unit tests pass cleanly.
- 10-tick mock dry run confirms no citizen goes un-reasoned for >3 ticks.
- 30-tick test run exports a valid, populated historical CSV.

```

---

### **Phase 4: FastAPI Backend (Engine & Endpoints)**

```
ROLE: Backend Developer. Build Phase 4 of 5: FastAPI Core Services.

SYSTEM CONTEXT:
Wrap the data, agent layer, rules, and scheduler inside a FastAPI framework. Build a continuous `SimulationEngine` background worker clock (1 tick = 1 day) managed as an asyncio task. Offload blocking, synchronous CrewAI agent runs into a distinct thread pool via `asyncio.to_thread` to preserve API responsiveness. 

FILE STRUCTURE DIRECTIVES:
- `autosociety/requirements.txt` — Add: fastapi, uvicorn[standard]
- `autosociety/backend/main.py` — Entry application instance with global middleware, lifespans, and CORS configurations.
- `autosociety/backend/routers/__init__.py` — [Empty]
- `autosociety/backend/routers/simulation.py` — Endpoints: `POST /start-simulation`, `/pause-simulation`, `/reset-simulation`, `GET /get-world-state`.
- `autosociety/backend/routers/queries.py` — Endpoints: `GET /get-citizens`, `/get-citizens/{id}`, `/get-policies`, `/get-events`, `/get-analytics`, `/get-reports`.
- `autosociety/backend/core/engine.py` — `SimulationEngine` class coordinating loop advancement, async worker threads, policy triggers, and database writing.
- `autosociety/tests/test_api.py` — Pytest endpoints suite using `fastapi.testclient.TestClient`.

STRICT CONSTRAINTS:
1. Blocked/synchronous LLM tasks must run inside `asyncio.to_thread(...)`.
2. Enforce strict Pydantic model response/request validations.
3. Ensure simulation state can pause and resume seamlessly without drop-outs or state wipes.
4. Integrate with 9Router endpoint configurations (`http://127.0.0.1:20128/v1`). 

DEFINITION OF DONE:
- Application starts up successfully via `uvicorn backend.main:app --reload`.
- State endpoints match exact structural JSON profiles.
- Automated API integration test suite achieves 100% execution pass rate.

```

---

### **Phase 5: Streamlit Dashboard (UI & Polling)**

```
ROLE: Frontend UI Developer. Build Phase 5 of 5: Streamlit Interface.

SYSTEM CONTEXT:
Build a data visualization and control UI consuming the FastAPI REST endpoints. The client app must remain completely detached from storage engines; zero imports from SQLite or ChromaDB are permitted here. Fetch changes dynamically via client-side REST polling.

FILE STRUCTURE DIRECTIVES:
- `autosociety/requirements.txt` — Add: streamlit, plotly, requests
- `autosociety/frontend/app.py` — Interface dashboard entry: sidebar routing, system clock control toggles, macro KPI Plotly widgets, and a background interval polling utility (2-3 seconds threshold).
- `autosociety/frontend/pages/1_Analytics.py` — Macro trends explorer (GDP velocity, employment, demographic indicators).
- `autosociety/frontend/pages/2_Government.py` — Legislative ledger displaying statutory adjustments and budget breakdowns.
- `autosociety/frontend/pages/3_Citizens.py` — Society browser detailing attributes and active networks.
- `autosociety/frontend/components/__init__.py` — [Empty]
- `autosociety/frontend/components/charts.py` — Shared abstraction module handling uniform Plotly chart building.
- `autosociety/run_sim.py` — Combined bootstrap utility running both application layers simultaneously as parallel subprocesses.

STRICT CONSTRAINTS:
1. Zero database or vector-store dependencies are allowed under the `frontend/` scope.
2. Restrict UI data fetching to a 2-3 second execution loop using `st.session_state` and a time component to prevent API overloading.
3. Catch connection failures gracefully; present clean warning banners instead of stack traces if the engine goes offline.

DEFINITION OF DONE:
- Executing `python run_sim.py` boots both application servers in parallel.
- Clicking the dashboard controls modifies loop states live on screen.
- All system pages load completely using asynchronous API calls.

```