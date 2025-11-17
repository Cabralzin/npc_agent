from core.state import NPCState
from core.memory import SemanticMemory
from tools.lore import recall_fact
from core.world_lore import WORLD_LORE

async def world_model(state: NPCState) -> NPCState:
    q = state["scratch"].get("event_summary", "")
    if not q:
        return state
    # usando stub de memória semântica via ferramenta
    # (em produção, injete um retriever)
    mem = SemanticMemory(lore_docs=WORLD_LORE)
    lore = recall_fact.run(q, mem=mem)  # type: ignore
    state["scratch"]["lore_hits"] = lore
    return state
