from langchain_core.messages import SystemMessage, HumanMessage
import logging
from core.llm import LLMHarness
from core.state import NPCState
from graph.prompts import sys_persona

_llm = LLMHarness()
_logger = logging.getLogger("npc.agents.planner")

async def planner(state: NPCState) -> NPCState:
    persona = state["persona"]
    lore = state["scratch"].get("lore_hits", "")
    emotions = ", ".join(f"{k}:{v:.2f}" for k, v in state.get("emotions", {}).items()) or "neutro"
    prompt = [
        sys_persona(persona),
        SystemMessage(content=(
            "Você é o Planejador Interno do NPC. Proponha uma intenção de alto nível "
            "com base nos eventos, emoções e fatos. Seja curto e objetivo.\n"
            "Formato de saída (linhas separadas, sem comentários):\n"
            "INTENÇÃO: <texto curto>\n"
            "NEEDS_WORLD: <yes|no>\n"
            "WORLD_QUERY: <se NEEDS_WORLD=yes, uma consulta objetiva ao mundo; caso contrário, deixe vazio>"
        )),
        HumanMessage(content=f"EVENTOS: {state['scratch'].get('event_summary','(n/a)')}"),
        HumanMessage(content=f"EMOÇÕES: {emotions}"),
        HumanMessage(content=f"LORE:\n{lore}"),
    ]
    _logger.info("planner.in: emotions=%s has_lore=%s", emotions, bool(lore))
    text = await _llm.run(prompt)
    raw = text.strip()
    intent = None
    needs_world = False
    world_query = ""
    for line in raw.splitlines():
        l = line.strip()
        if l.upper().startswith("INTENÇÃO:"):
            intent = l.split(":", 1)[1].strip()
        elif l.upper().startswith("NEEDS_WORLD:"):
            val = l.split(":", 1)[1].strip().lower()
            needs_world = val in ("yes", "sim", "true")
        elif l.upper().startswith("WORLD_QUERY:"):
            world_query = l.split(":", 1)[1].strip()
    if not intent:
        intent = raw
    if needs_world and not world_query:
        world_query = state["scratch"].get("event_summary") or ""
    state["intent"] = intent
    state["scratch"]["needs_world"] = needs_world
    if needs_world and world_query:
        state["scratch"]["world_query"] = world_query
    _logger.info("planner.out: intent=%s needs_world=%s has_query=%s", intent, needs_world, bool(world_query))
    return state
