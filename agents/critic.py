from langchain_core.messages import SystemMessage, HumanMessage
import logging

from core.llm import LLMHarness
from core.state import NPCState
from graph.prompts import sys_persona
from core.voice import synthesize_npc_voice_bytes

_llm = LLMHarness()
_logger = logging.getLogger("npc.agents.critic")


async def critic(state: NPCState) -> NPCState:
    persona = state["persona"]
    reply = state["scratch"].get("candidate_reply", "") or ""
    lore = state["scratch"].get("lore_hits", "") or ""
    intent = state.get("intent", "") or ""
    emotions_dict = state.get("emotions", {}) or {}

    emotions = ", ".join(f"{k}:{v:.2f}" for k, v in emotions_dict.items()) or "neutro"

    prompt = [
        sys_persona(persona),
        SystemMessage(
            content=(
                "Você é o Crítico Interno do NPC. Sua função é revisar a fala proposta pelo agente de diálogo.\n"
                "\n"
                "⚠️ REGRA PRINCIPAL:\n"
                "- SOMENTE EDITE a fala se houver necessidade real.\n"
                "- Se a resposta proposta já estiver boa, natural, coerente com a persona e com o mundo, "
                "mantenha-a intacta.\n"
                "- Ajuste apenas quando houver problemas de tom, coerência, clareza, estilo ou se puder "
                "suavemente aprimorar o impacto emocional.\n"
                "- Evite reescrever completamente quando não for necessário.\n"
                "\n"
                "REGRAS GERAIS:\n"
                "- Mantenha a personalidade, voz e estilo de fala da persona.\n"
                "- Respeite o tom do mundo e qualquer lore fornecido.\n"
                "- Se for usar o lore, use-o de maneira sutil, orgânica e opcional. Não insira se não fizer sentido.\n"
                "- Incorpore 'intenção' e 'emoções' apenas como subtexto natural na fala; nunca cite esses termos.\n"
                "- Falas devem soar naturais para um NPC, não como narração em terceira pessoa.\n"
                "- Prefira respostas curtas a médias, adequadas a diálogo em jogo.\n"
                "- NÃO explique o que está fazendo, não comente sobre 'resposta proposta', 'lore' ou sistema.\n"
                "\n"
                "SAÍDA:\n"
                "- Retorne APENAS a fala final do NPC.\n"
                "- Sem aspas, sem markdown, sem explicações."
            )
        ),
        HumanMessage(
            content=f"CONTEXTO ATUAL: INTENÇÃO={intent} | EMOÇÕES={emotions}"
        ),
        HumanMessage(
            content=(
                "RESPOSTA PROPOSTA DO NPC (avaliar e editar apenas se necessário):\n"
                f"{reply}\n\n"
                "TRECHOS DE LORE (use apenas se relevante):\n"
                f"{lore}"
            )
        ),
    ]

    _logger.info(
        "critic.in: has_reply=%s lore_len=%s intent=%s emotions=%s",
        bool(reply),
        len(str(lore)),
        intent,
        emotions,
    )

    text = await _llm.run(prompt)
    final = (text or "").strip().strip('"').strip("'")

    _logger.info("critic.out: %s\n", final)

    # fala final no scratch
    state["scratch"]["final_reply"] = final

    # gera áudio em memória (não salva em disco)
    audio_bytes = None
    try:
        audio_bytes = synthesize_npc_voice_bytes(final, persona)
    except Exception as e:
        _logger.exception("critic.tts_error: %s", e)

    # ação final para o runtime
    action = {
        "type": "say",
        "content": final,
    }
    if audio_bytes is not None:
        # o engine do jogo decide como usar esses bytes (stream, websocket, etc.)
        action["audio"] = audio_bytes

    state["action"] = action
    return state