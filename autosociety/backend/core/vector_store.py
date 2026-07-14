import os
from pathlib import Path
import chromadb
from typing import List, Dict, Optional

# Data storage directory setup
_data_dir_env = os.getenv("AUTOSOCIETY_DATA_DIR")
if _data_dir_env:
    DATA_DIR = Path(_data_dir_env)
else:
    DATA_DIR = Path(__file__).parent.parent.parent.parent / "data_storage"
DATA_DIR.mkdir(exist_ok=True)
CHROMA_DIR = DATA_DIR / "chroma_db"
CHROMA_DIR.mkdir(exist_ok=True)

# ChromaDB setup
client = chromadb.PersistentClient(path=str(CHROMA_DIR))
MEMORIES_COLLECTION = "agent_memories"


def get_memories_collection():
    """Get or create the agent memories collection."""
    return client.get_or_create_collection(
        name=MEMORIES_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )


def add_memory(citizen_id: int, text: str, metadata: Optional[Dict] = None) -> str:
    """
    Add a memory for a citizen.

    Args:
        citizen_id: ID of the citizen
        text: Memory text content
        metadata: Optional metadata dict

    Returns:
        The document ID
    """
    collection = get_memories_collection()
    doc_id = f"citizen_{citizen_id}_memory_{collection.count() + 1}"

    if metadata is None:
        metadata = {}
    metadata["citizen_id"] = citizen_id

    collection.add(
        ids=[doc_id],
        documents=[text],
        metadatas=[metadata]
    )
    return doc_id


def search_memory(citizen_id: int, query: str, k: int = 5) -> List[Dict]:
    """
    Search memories for a specific citizen.

    Args:
        citizen_id: ID of the citizen
        query: Search query text
        k: Number of results to return

    Returns:
        List of matching memories with scores
    """
    collection = get_memories_collection()

    results = collection.query(
        query_texts=[query],
        n_results=k,
        where={"citizen_id": citizen_id}
    )

    # Format results
    formatted_results = []
    if results and results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            formatted_results.append({
                "id": results["ids"][0][i],
                "text": doc,
                "distance": results["distances"][0][i] if results["distances"] else None,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
            })

    return formatted_results


def get_all_memories(citizen_id: int) -> List[Dict]:
    """
    Get all memories for a specific citizen.

    Args:
        citizen_id: ID of the citizen

    Returns:
        List of all memories
    """
    collection = get_memories_collection()

    results = collection.get(
        where={"citizen_id": citizen_id}
    )

    formatted_results = []
    if results and results["documents"]:
        for i, doc in enumerate(results["documents"]):
            formatted_results.append({
                "id": results["ids"][i],
                "text": doc,
                "metadata": results["metadatas"][i] if results["metadatas"] else {}
            })

    return formatted_results


def delete_memory(memory_id: str) -> bool:
    """Delete a specific memory."""
    collection = get_memories_collection()
    try:
        collection.delete(ids=[memory_id])
        return True
    except Exception:
        return False


def clear_citizen_memories(citizen_id: int) -> int:
    """Delete all memories for a citizen. Returns count deleted."""
    collection = get_memories_collection()
    results = collection.get(where={"citizen_id": citizen_id})

    if results and results["ids"]:
        collection.delete(ids=results["ids"])
        return len(results["ids"])
    return 0
