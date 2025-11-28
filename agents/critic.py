from langchain_core.messages import SystemMessage, HumanMessage
import logging
import json

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
                "Você é o Crítico Interno do NPC. Sua função é adaptar a fala proposta para ser NATURALMENTE FALADA, "
                "não apenas lida.\n"
                "\n"
                "⚠️ FOCO PRINCIPAL: FALA NATURAL PARA SER DITA EM VOZ ALTA\n"
                "- A fala será convertida em áudio por TTS (text-to-speech).\n"
                "- Adapte o texto para soar natural quando FALADO, não apenas quando lido.\n"
                "- Considere ritmo, pausas, respiração e entonação natural.\n"
                "\n"
                "REGRAS DE FALA NATURAL:\n"
                "- Use frases mais curtas e diretas (evite períodos muito longos).\n"
                "- Quebre frases longas em múltiplas sentenças mais curtas.\n"
                "- Use vírgulas e pontos para criar pausas naturais.\n"
                "- Evite construções muito formais ou literárias - prefira linguagem conversacional.\n"
                "- Use contrações quando apropriado para a persona (ex: 'tô', 'tá', 'pra').\n"
                "- Evite listas longas - se necessário, use 'e' entre itens para fluidez.\n"
                "- Prefira palavras mais curtas e diretas quando possível.\n"
                "- Evite repetições desnecessárias de palavras.\n"
                "\n"
                "REGRAS DE PERSONALIDADE E COERÊNCIA:\n"
                "- Mantenha a personalidade, voz e estilo de fala da persona.\n"
                "- Respeite o tom do mundo e qualquer lore fornecido.\n"
                "- Se for usar o lore, use-o de maneira sutil, orgânica e opcional.\n"
                "- Incorpore 'intenção' e 'emoções' apenas como subtexto natural na fala.\n"
                "- Falas devem soar como diálogo real, não como narração.\n"
                "\n"
                "QUANDO EDITAR:\n"
                "- SOMENTE edite se a fala precisar ser adaptada para fala natural.\n"
                "- Se já estiver natural para ser falada, mantenha quase intacta.\n"
                "- Ajuste principalmente: frases muito longas, construções formais, ritmo inadequado.\n"
                "- Evite reescrever completamente - faça ajustes cirúrgicos.\n"
                "\n"
                "FORMATO DE SAÍDA:\n"
                "- Se você FIZER ALTERAÇÕES na fala, retorne um JSON com:\n"
                "  {\n"
                "    \"fala\": \"<fala final otimizada>\",\n"
                "    \"justificativa\": \"<explicação breve do motivo da alteração>\"\n"
                "  }\n"
                "- Se você NÃO FIZER ALTERAÇÕES (manteve a fala original), retorne APENAS a fala final como texto simples.\n"
                "- A fala deve estar otimizada para ser FALADA naturalmente.\n"
                "- Sem aspas extras, sem markdown, sem explicações fora do JSON.\n"
                "- Foque em como soará quando convertida em voz."
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
    text = (text or "").strip()

    # Tenta parsear como JSON (se houver alterações)
    final = ""
    justificativa = ""

    try:
        # Remove markdown code blocks se houver
        if text.startswith("```"):
            first_newline = text.find("\n")
            last_backtick = text.rfind("```")
            if first_newline != -1 and last_backtick != -1:
                text = text[first_newline + 1:last_backtick].strip()

        # Tenta parsear como JSON
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            final = parsed.get("fala", "").strip().strip('"').strip("'")
            justificativa = parsed.get("justificativa", "").strip()
        else:
            # Se não for dict, trata como texto simples
            final = text.strip().strip('"').strip("'")
    except (json.JSONDecodeError, AttributeError):
        # Se não for JSON válido, trata como texto simples (sem alterações)
        final = text.strip().strip('"').strip("'")

    _logger.info("critic.out: %s\n", final)
    if justificativa:
        _logger.info("critic.justificativa: %s\n", justificativa)

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
