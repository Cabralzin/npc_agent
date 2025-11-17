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
            "Formato: INTENÇÃO: <texto>"
        )),
        HumanMessage(content=f"EVENTOS: {state['scratch'].get('event_summary','(n/a)')}"),
        HumanMessage(content=f"EMOÇÕES: {emotions}"),
        HumanMessage(content=f"LORE:\n{lore}"),
    ]
    _logger.info("planner.in: emotions=%s has_lore=%s", emotions, bool(lore))
    text = await _llm.run(prompt)
    intent = text.strip()
    _logger.info("planner.out: %s", intent)
    state["intent"] = intent
    return state
