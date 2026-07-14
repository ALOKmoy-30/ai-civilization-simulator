"""
Pytest suite for vector_store.py

Note: Uses module-level setup to avoid Windows file locking issues with ChromaDB.
"""

import pytest
import shutil
from pathlib import Path

from autosociety.backend.core import vector_store
from autosociety.backend.core.vector_store import (
    add_memory,
    search_memory,
    get_all_memories,
    delete_memory,
    clear_citizen_memories,
    CHROMA_DIR,
    client,
)


# Use module-level setup to avoid file locking on Windows
@pytest.fixture(scope="module", autouse=True)
def setup_chroma():
    """Set up ChromaDB once for all tests."""
    # Ensure directory exists
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # No teardown - leave ChromaDB intact to avoid Windows file locking


def test_add_memory():
    """Test adding a memory."""
    doc_id = add_memory(
        citizen_id=100,
        text="I met John at the coffee shop today.",
        metadata={"type": "social", "day": 1},
    )
    assert doc_id is not None
    assert "citizen_100_memory_" in doc_id


def test_search_memory():
    """Test searching for a memory."""
    add_memory(
        citizen_id=200,
        text="I went to the park and saw beautiful flowers.",
        metadata={"type": "personal"},
    )
    add_memory(
        citizen_id=200,
        text="The economic situation is improving.",
        metadata={"type": "observation"},
    )

    results = search_memory(citizen_id=200, query="flowers and nature", k=5)

    assert len(results) >= 1
    assert "flowers" in results[0]["text"]
    assert results[0]["metadata"]["citizen_id"] == 200


def test_search_memory_isolated():
    """Test that search only returns memories for specified citizen."""
    add_memory(citizen_id=300, text="I enjoy playing tennis.")
    add_memory(citizen_id=400, text="I love cooking pasta.")

    results_3 = search_memory(citizen_id=300, query="sports and hobbies", k=5)
    results_4 = search_memory(citizen_id=400, query="sports and hobbies", k=5)

    # Each search should only return their own memories
    assert all(r["metadata"]["citizen_id"] == 300 for r in results_3)
    assert all(r["metadata"]["citizen_id"] == 400 for r in results_4)


def test_get_all_memories():
    """Test retrieving all memories for a citizen."""
    add_memory(citizen_id=500, text="Memory 1 for citizen 500")
    add_memory(citizen_id=500, text="Memory 2 for citizen 500")
    add_memory(citizen_id=500, text="Memory 3 for citizen 500")
    add_memory(citizen_id=600, text="Other citizen memory")

    memories = get_all_memories(citizen_id=500)

    assert len(memories) >= 3
    assert all(m["metadata"]["citizen_id"] == 500 for m in memories)


def test_delete_memory():
    """Test deleting a specific memory."""
    doc_id = add_memory(citizen_id=700, text="Temporary memory to delete")

    success = delete_memory(doc_id)
    assert success is True

    # Verify it's gone
    all_memories = get_all_memories(citizen_id=700)
    assert not any(m["id"] == doc_id for m in all_memories)


def test_clear_citizen_memories():
    """Test clearing all memories for a citizen."""
    add_memory(citizen_id=800, text="Memory A for 800")
    add_memory(citizen_id=800, text="Memory B for 800")
    add_memory(citizen_id=900, text="Other citizen 900")

    count = clear_citizen_memories(citizen_id=800)

    assert count >= 2
    assert len(get_all_memories(citizen_id=800)) == 0


def test_memory_persistence():
    """Test that memories persist across collection calls."""
    add_memory(citizen_id=1000, text="Persistent memory test", metadata={"key": "value"})

    results = search_memory(citizen_id=1000, query="persistent", k=5)

    assert len(results) >= 1
    found = any("Persistent memory test" in r["text"] for r in results)
    assert found
