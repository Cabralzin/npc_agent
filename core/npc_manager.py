from typing import Dict, Optional, List, Any
from core.persona import Persona, DEFAULT_PERSONA
from graph.runtime import NPCGraph
from core.json_memory import JSONMemoryStore

class NPCManager:
    def __init__(self):
        self._graphs: Dict[str, NPCGraph] = {}

    def register(
        self,
        npc_id: str,
        persona: Optional[Persona] = None,
        *,
        initial_memories: Optional[List[Any]] = None,
    ) -> None:
        if npc_id not in self._graphs:
            graph = NPCGraph(persona=persona or DEFAULT_PERSONA, npc_id=npc_id)
            self._graphs[npc_id] = graph
            if initial_memories:
                self.seed_memories(npc_id, initial_memories)

    def get(self, npc_id: str) -> NPCGraph:
        if npc_id not in self._graphs:
            # Auto-register with default persona if not present
            self.register(npc_id)
        return self._graphs[npc_id]

    async def respond_once(
        self,
        npc_id: str,
        user_text: str,
        *,
        thread_id: Optional[str] = None,
        events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        graph = self.get(npc_id)
        return await graph.respond_once(user_text, thread_id=thread_id, events=events)

    def seed_memories(self, npc_id: str, entries: List[Any]) -> None:
        graph = self.get(npc_id)
        store: JSONMemoryStore = graph.store
        for e in entries:
            if isinstance(e, str):
                rec = store.minimal_record(
                    user_text="[seed]",
                    reply_text=None,
                    intent=None,
                    action={"type": "seed"},
                    events=None,
                    extras={"note": e},
                )
                store.append(rec)
            elif isinstance(e, dict):
                store.append(e)
