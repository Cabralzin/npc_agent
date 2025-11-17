from langchain.tools import tool
from typing import Optional
from core.memory import SemanticMemory

@tool
def recall_fact(query: str, mem: Optional[SemanticMemory] = None) -> str:
    """Search for relevant information in the NPC's semantic memory.
    
    Args:
        query: The search query to find relevant information
        mem: Optional SemanticMemory instance to search in
        
    Returns:
        str: The most relevant information found, or a message if nothing is found
    """
    if not mem:
        return "[no semantic memory configured]"
    hits = mem.search(query, k=3)
    if not hits:
        return "[no results]"
    return "\n---\n".join(hits)