from langchain_core.messages import SystemMessage, HumanMessage
from langchain.messages 
from core.llm import LLMHarness
from core.state import NPCState
from graph.prompts import sys_persona

_llm = LLMHarness()

async def critic(state: NPCState) -> NPCState:
    persona = state["persona"]
    reply = state["scratch"].get("candidate_reply", "")
    lore = state["scratch"].get("lore_hits", "")
    prompt = [
        sys_persona(persona),
        SystemMessage(content=(
            "Você é o Crítico Interno. Verifique a resposta proposta:\n"
            "- condiz com a personalidade/objetivos?\n"
            "- coerente com o lore?\n"
            "Se necessário, reescreva mantendo intenção e tom.\n"
            "Responda apenas com a versão final."
        )),
        HumanMessage(content=f"RESPOSTA PROPOSTA:\n{reply}\n\nLORE:\n{lore}"),
    ]
    text = await _llm.run(prompt)
    state["scratch"]["final_reply"] = text.strip()
    return state