from langchain_core.messages import SystemMessage, HumanMessage
import logging
from core.llm import LLMHarness
from core.state import NPCState
from graph.prompts import sys_persona

_llm = LLMHarness()
_logger = logging.getLogger("npc.agents.dialogue")


DIALOGUE_SYS_PROMPT = """
Você é o MÓDULO DE DIÁLOGO de um NPC em um RPG de mesa.

OBJETIVO
- Sua tarefa é propor a fala do NPC para o jogador/GM e, em seguida,
  produzir uma breve análise para o agente CRÍTICO.
- Sua resposta NÃO vai diretamente para o jogador — é apenas uma
  SUGESTÃO para revisão posterior.

ESTILO
- Mantenha coerência com a PERSONA.
- Respostas curtas, naturais, 1–3 frases.
- Evite listas e bullets.
- Utilize a INTENÇÃO fornecida para orientar a fala.

FORMATO DE SAÍDA (OBRIGATÓRIO)

FALA_NPC:
<fala proposta, 1–3 frases>

NOTA_CRITICO:
- coerencia_plano_objetivo: <curto>
- aderencia_personalidade_emocao: <curto>
- risco_conteudo: <baixo/médio/alto + justificativa>
- observacoes: <curto>

NUNCA escreva fora desse formato.
"""


async def dialogue(state: NPCState) -> NPCState:
    persona = state["persona"]
    scratch = state.get("scratch") or {}
    state["scratch"] = scratch

    last_user = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        None
    )
    user_text = last_user.content if last_user else "(sem fala do jogador)"

    intent = state.get("intent", "")
    lore = scratch.get("lore_hits", "")

    _logger.info(
        "dialogue.in: has_intent=%s user_len=%s has_lore=%s",
        bool(intent), len(str(user_text)), bool(lore)
    )

    prompt = [
        sys_persona(persona),
        SystemMessage(content=DIALOGUE_SYS_PROMPT),
        HumanMessage(content=f"INTENÇÃO_ATUAL:\n{intent}"),
    ]

    if lore:
        prompt.append(HumanMessage(content=f"INFORMAÇÕES_DE_MUNDO:\n{lore}"))

    # Incluindo variáveis importantes do scratch (compatível com nosso modelo)
    contexto_scratch = (
        f"Plano: {scratch.get('plan')}\n"
        f"Objetivo imediato: {scratch.get('current_goal')}\n"
        f"Percepção: {scratch.get('perceived_context')}\n"
        f"Pistas ambientais: {scratch.get('environmental_cues')}\n"
        f"Personalidade: {scratch.get('personality_analysis')}\n"
        f"Estado emocional: {scratch.get('emotional_state')}\n"
        f"Memórias relevantes: {scratch.get('relevant_memories')}\n"
        f"Conhecimento de mundo: {scratch.get('world_knowledge')}\n"
        f"Feedback do crítico anterior: {scratch.get('critic_feedback')}\n"
    )
    prompt.append(HumanMessage(content=f"CONTEXTO_INTERNO_NPC:\n{contexto_scratch}"))

    # Última fala do jogador
    prompt.append(HumanMessage(content=f"DERRADEIRA_FALA_DO_JOGADOR:\n{user_text}"))

    raw = await _llm.run(prompt)
    raw = raw.strip()

    fala = raw
    nota = ""

    if "NOTA_CRITICO:" in raw:
        head, tail = raw.split("NOTA_CRITICO:", 1)
        fala = head.replace("FALA_NPC:", "").strip()
        nota = tail.strip()
    else:
        if raw.startswith("FALA_NPC:"):
            fala = raw[len("FALA_NPC:"):].strip()


    scratch["candidate_reply"] = fala
    scratch["critic_feedback"] = nota

    _logger.info(
        "dialogue.out: candidate_len=%s critic_len=%s",
        len(fala), len(nota)
    )

    """
    npc_name = persona.name if hasattr(persona, "name") else "NPC"
    scratch["toon"] = {
        "type": "dialog",
        "character": npc_name,
        "text": fala,
        "emotion": scratch.get("emotional_state", "neutral"),
    }
    """

    return state
