from typing import Any, Dict, List, Optional, TypedDict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .persona import Persona


class ScratchState(TypedDict, total=False):
    # Saída do módulo de diálogo
    candidate_reply: str
    critic_feedback: str

    # Saída do módulo crítico
    final_reply: str
    critic_review: str

    # Formato TOON opcional (JToon)
    toon: Dict[str, Any]

    # Campos gerais
    plan: str
    current_goal: str
    perceived_context: str
    environmental_cues: str
    personality_analysis: str
    emotional_state: str
    relevant_memories: str
    world_knowledge: str

    # Snapshot de debug (opcional)
    context_snapshot: str


class NPCState(TypedDict):
    npc_id: str
    messages: List[Any]  # HumanMessage | AIMessage | SystemMessage
    events: List[Dict[str, Any]]
    intent: Optional[str]
    emotions: Dict[str, float]
    scratch: ScratchState
    action: Optional[Dict[str, Any]]
    persona: Persona
