from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

from autosociety.backend.core.vector_store import search_memory


class MemorySearchInput(BaseModel):
    query: str = Field(description="Search query for retrieving relevant memories")


class MemorySearchTool(BaseTool):
    """Tool that searches a citizen's memories via ChromaDB."""

    name: str = "MemorySearch"
    description: str = (
        "Search the citizen's past memories for relevant context. "
        "Input should be a query string describing what you want to recall. "
        "Returns up to 5 matching memories with relevance scores."
    )
    args_schema: Type[BaseModel] = MemorySearchInput
    citizen_id: int = 0

    def _run(self, query: str) -> str:
        results = search_memory(citizen_id=self.citizen_id, query=query, k=5)
        if not results:
            return "No relevant memories found."
        formatted = []
        for r in results:
            meta = r.get("metadata", {})
            tag = meta.get("type", "general")
            score = 1 - r.get("distance", 0)
            formatted.append(f"[{tag}] {r['text']} (relevance: {score:.2f})")
        return "\n".join(formatted)


def create_rag_tool(citizen_id: int) -> MemorySearchTool:
    return MemorySearchTool(citizen_id=citizen_id)
