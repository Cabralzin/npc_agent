from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import logging
from core.llm import LLMHarness
from core.state import NPCState
from graph.prompts import sys_persona

_llm = LLMHarness()
_logger = logging.getLogger("npc.agents.critic")

async def critic(state: NPCState) -> NPCState:
    persona = state["persona"]
    reply = state["scratch"].get("candidate_reply", "")
    lore = state["scratch"].get("lore_hits", "")
    intent = state.get("intent", "")
    emotions = ", ".join(f"{k}:{v:.2f}" for k, v in state.get("emotions", {}).items()) or "neutro"
    prompt = [
        sys_persona(persona),
        SystemMessage(content=(
            "Você é o Crítico Interno. Verifique a resposta proposta e, se necessário, reescreva.\n"
            "REGRAS:\n"
            "- Mantenha personalidade e lore.\n"
            "- Incorpore brevemente o contexto atual (intenção e humor) de forma natural na fala, como uma breve moldura ou subtexto, sem parecer meta.\n"
            "- Responda APENAS com a FALA FINAL do NPC, sem comentários, sem justificativas, sem aspas."
        )),
        HumanMessage(content=f"CONTEXTO: INTENÇÃO={intent} | EMOÇÕES={emotions}"),
        HumanMessage(content=f"RESPOSTA PROPOSTA:\n{reply}\n\nLORE:\n{lore}"),
    ]
    _logger.info("critic.in: has_reply=%s lore_len=%s", bool(reply), len(str(lore)))
    text = await _llm.run(prompt)
    final = text.strip().strip('"').strip("'")
    _logger.info("critic.out: %s", final)
    state["scratch"]["final_reply"] = final
    # Set the final action so runtime can return reply_text
    state["action"] = {"type": "say", "content": final}
    return state