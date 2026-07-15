"""
Manual test: build one citizen agent, run a decision, print the result.

Usage:
    python -m autosociety.scripts.test_single_citizen
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autosociety.agents.crews.citizen import build_citizen_agent, run_citizen_decision


def main():
    citizen_id = 1

    agent = build_citizen_agent(citizen_id)
    print(f"Built agent for: {agent.role}")
    print(f"Goal: {agent.goal[:120]}...")
    print(f"Tools: {[t.name for t in (agent.tools or [])]}")
    print()

    situation = (
        "A new community center has been proposed in your neighborhood. "
        "It would require a small tax increase but provide recreational activities for all ages."
    )

    print(f"Situation: {situation}\n")
    print("Running citizen decision cycle (observe → RAG → reason → decide)...\n")

    start = time.monotonic()
    result = run_citizen_decision(citizen_id, situation)
    elapsed = time.monotonic() - start

    print("=" * 60)
    print("DECISION RESULT")
    print("=" * 60)
    print(f"Citizen: {result['name']} (ID: {result['citizen_id']})")
    print(f"Decision:\n{result['decision']}")
    print(f"\nEffects: {result['effects']}")
    print(f"\nWall-clock time: {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
