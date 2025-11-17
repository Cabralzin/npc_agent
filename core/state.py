from typing import Any, Dict, List, Optional, TypedDict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .persona import Persona

class NPCState(TypedDict):
    npc_id: str
    messages: List[Any]  # HumanMessage | AIMessage | SystemMessage
    events: List[Dict[str, Any]]
    intent: Optional[str]
    emotions: Dict[str, float]
    scratch: Dict[str, Any]
    action: Optional[Dict[str, Any]]
    persona: Persona