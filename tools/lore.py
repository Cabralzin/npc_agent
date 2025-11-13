from langchain.tools import tool
from typing import Optional
from core.memory import SemanticMemory

@tool
def recall_fact(query: str, mem: Optional[SemanticMemory] = None) -> str:
    if not mem:
        return "[no semantic memory configured]"
    hits = mem.search(query, k=3)
    if not hits:
        return "[no results]"
    return "\n---\n".join(hits)