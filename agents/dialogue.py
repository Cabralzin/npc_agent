from langchain_core.messages import SystemMessage, HumanMessage
from core.llm import LLMHarness
from core.state import NPCState
from graph.prompts import sys_persona

_llm = LLMHarness()

async def dialogue(state: NPCState) -> NPCState:
    persona = state["persona"]
    last_user = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    user_text = last_user.content if last_user else "(sem fala do jogador)"
    prompt = [
        sys_persona(persona),
        SystemMessage(content=(
            "Você é o Gerador de Diálogo. Produza a fala do NPC ao jogador/GM. "
            "Leve em conta a INTENÇÃO proposta e mantenha o tom de voz. "
            "Respostas curtas, naturais para fala; evite listas."
        )),
        HumanMessage(content=f"INTENÇÃO: {state.get('intent','(n/a)')}"),
        HumanMessage(content=f"DERRADEIRA FALA DO JOGADOR: {user_text}"),
    ]
    text = await _llm.run(prompt)
    state["scratch"]["candidate_reply"] = text.strip()
    return state
