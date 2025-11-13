from core.state import NPCState
from core.memory import SemanticMemory
from tools.lore import recall_fact

async def world_model(state: NPCState) -> NPCState:
    q = state["scratch"].get("event_summary", "")
    if not q:
        return state
    # usando stub de memória semântica via ferramenta
    # (em produção, injete um retriever)
    mem = SemanticMemory(lore_docs=[
        "A Rota Norte passa pela Ponte do Carvalho; guardas cobram pedágio ilegal.",
        "A Guilda das Sombras opera em tavernas com janelas vermelhas.",
        "Neblina densa ao amanhecer no Vale da Névoa facilita emboscadas.",
    ])
    lore = recall_fact.run(q, mem=mem)  # type: ignore
    state["scratch"]["lore_hits"] = lore
    return state
