import logging
from core.state import NPCState
from core.memory import SemanticMemory
from core.world_lore import WORLD_LORE

_logger = logging.getLogger("npc.agents.world_model")


async def world_model(state: NPCState) -> NPCState:
    q = state["scratch"].get("world_query") or state["scratch"].get("event_summary", "")
    _logger.info("world_model.in: has_query=%s query=%s", bool(q), q)
    if not q:
        return state
    # usando stub de memória semântica via ferramenta
    # (em produção, injete um retriever)
    mem = SemanticMemory(lore_docs=WORLD_LORE)

    # Busca os hits diretamente para poder logar quais informações foram acessadas
    hits = mem.search(q, k=3)
    if not hits:
        lore = "[no results]"
        _logger.info("world_model.info_acessada: query=%s hits=nenhum resultado encontrado", q)
    else:
        lore = "\n---\n".join(hits)
        # Log detalhado de quais informações foram acessadas
        for i, hit in enumerate(hits, 1):
            _logger.info("world_model.info_acessada: query=%s hit_%d=%s", q, i, hit)

    state["scratch"]["lore_hits"] = lore
    _logger.info("world_model.out: lore_len=%s lore=%s\n", len(str(lore)), lore)
    return state
