from langchain_core.messages import SystemMessage, HumanMessage
import logging
import json
import re
from typing import Optional

from core.llm import LLMHarness
from core.state import NPCState
from graph.prompts import sys_persona
from core.voice import synthesize_npc_voice_bytes
from core.relationship_store import RelationshipStore
from core.models_preset import CRITIC_MODEL

_llm = LLMHarness(model=CRITIC_MODEL)
_logger = logging.getLogger("npc.agents.critic")


def extract_character_name(user_text: str, npc_name: str) -> Optional[str]:
    """Tenta extrair o nome do personagem da mensagem do usuário, ignorando o nome do NPC."""
    if not user_text:
        return None

    # Padrões comuns: "Nome: mensagem" ou "Nome disse: mensagem"
    patterns = [
        r"^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*):\s+(.+)$",  # "Nome: mensagem"
        r"^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+disse[:\s]+(.+)$",  # "Nome disse: mensagem"
    ]

    for pattern in patterns:
        match = re.match(pattern, user_text.strip())
        if match:
            name = match.group(1).strip()
            # Ignora se for o nome do NPC
            if npc_name and name.lower() == npc_name.lower():
                continue
            # Ignora nomes muito curtos ou muito longos
            if 2 <= len(name) <= 30:
                return name

    # Se não encontrou padrão, tenta pegar a primeira palavra se for capitalizada
    words = user_text.strip().split()
    if words and words[0][0].isupper() and len(words[0]) >= 2:
        common_starters = ["Eu", "Você", "Ele", "Ela", "Nós", "Eles", "Elas", "O", "A", "Os", "As", "Um", "Uma"]
        if words[0] not in common_starters:
            if npc_name and words[0].lower() != npc_name.lower():
                return words[0]
            elif not npc_name:
                return words[0]

    return None


async def critic(state: NPCState) -> NPCState:
    persona = state["persona"]
    scratch = state.get("scratch", {}) or {}
    reply = scratch.get("candidate_reply", "") or ""
    lore = scratch.get("lore_hits", "") or ""
    intent = state.get("intent", "") or ""
    emotions_dict = state.get("emotions", {}) or {}

    # Informações de personalidade e estado mental do scratch
    personality_analysis = scratch.get("personality_analysis", "") or ""
    emotional_state = scratch.get("emotional_state", "") or ""
    relevant_memories = scratch.get("relevant_memories", "") or ""
    world_knowledge = scratch.get("world_knowledge", "") or ""
    perceived_context = state.get("perceived_context", "") or scratch.get("perceived_context", "") or ""
    environmental_cues = state.get("environmental_cues", "") or scratch.get("environmental_cues", "") or ""
    plan = scratch.get("plan", "") or ""
    current_goal = scratch.get("current_goal", "") or ""

    # Informações de relacionamento
    npc_id = state.get("npc_id", "")
    npc_name = persona.name if persona else ""
    relationship_info = ""

    # Tenta extrair o nome do personagem que está falando
    last_user_message = next(
        (m for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)),
        None
    )
    if last_user_message:
        user_text = last_user_message.content if hasattr(last_user_message, 'content') else str(last_user_message)
        character_name = extract_character_name(user_text, npc_name)
        if character_name:
            relationship_store = RelationshipStore(npc_id)
            relationship = relationship_store.get_relationship(character_name)
            if relationship:
                relationship_info = (
                    f"RELACIONAMENTO COM {character_name}:\n"
                    f"- Confiança: {relationship.get('trust', 0.5):.2f}\n"
                    f"- Medo: {relationship.get('fear', 0.0):.2f}\n"
                    f"- Respeito: {relationship.get('respect', 0.5):.2f}\n"
                    f"- Apego: {relationship.get('attachment', 0.0):.2f}\n"
                    f"- Hostilidade: {relationship.get('hostility', 0.0):.2f}\n"
                    f"- Dependência: {relationship.get('dependance', 0.0):.2f}\n"
                )
                if relationship.get('betrayal_memory'):
                    relationship_info += f"- Memória de traição: {relationship['betrayal_memory']}\n"

    emotions = ", ".join(f"{k}:{v:.2f}" for k, v in emotions_dict.items()) if emotions_dict else "neutro"

    prompt = [
        sys_persona(persona),
        SystemMessage(
            content=(
                "Você é o Crítico Interno do NPC. Sua função é deixar a fala parecida com como as pessoas falam no dia a dia. Use gírias, expressões rápidas, hesitações, cortes de frase, risadas, risadas de chateamento e até erros leves que pareçam naturais.\n"
                "como um diálogo humano real, não um texto escrito.\n"
                "⚠️ FOCO PRINCIPAL: FALA HUMANA PARA SER DITA EM VOZ ALTA\n"
                "- A fala será convertida em áudio por TTS.\n"
                "- Ajuste para soar espontânea, fluida e orgânica.\n"
                "- Considere ritmo, pausas, respiração, hesitações naturais e entonação.\n"
                "- A fala deve parecer saída da boca de um ser humano, não de um narrador.\n"
                "\n"
                "REGRAS DE FALA HUMANA:\n"
                "- Frases mais curtas e diretas.\n"
                "- Quebre frases longas em sentenças simples.\n"
                "- Use vírgulas, pausas e variações de ritmo naturais.\n"
                "- Evite formalidade excessiva; use linguagem conversacional.\n"
                "- Use contrações e expressões próprias da persona ('tô', 'cê', 'pra', etc., se combinarem com o estilo dela).\n"
                "- Inclua hesitações leves quando natural à personagem: 'é...', 'hm', 'olha...'.\n"
                "- Evite listas longas; prefira encadear ideias naturalmente.\n"
                "- Prefira palavras curtas e de uso comum.\n"
                "- Evite repetição desnecessária.\n"
                "- Priorize ritmo e musicalidade da fala.\n"
                "\n"
                "REGRAS DE PERSONALIDADE E COERÊNCIA:\n"
                "- Preserve a personalidade, voz, emoções e maneirismos da persona.\n"
                "- Use TODAS as informações fornecidas (análise de personalidade, estado emocional, relacionamentos, memórias, contexto) para ajustar a fala.\n"
                "- A fala deve refletir o estado emocional atual do NPC de forma sutil e natural.\n"
                "- Considere o relacionamento com o personagem que está falando (confiança, medo, hostilidade, etc.) ao ajustar o tom.\n"
                "- Use memórias relevantes e conhecimento de mundo se fluírem naturalmente na conversa.\n"
                "- O contexto percebido e pistas ambientais podem influenciar o tom e a escolha de palavras.\n"
                "- Mantenha coerência com o mundo e o lore.\n"
                "- Use referências ao lore apenas se fluírem naturalmente.\n"
                "- Emoções não devem ser explicadas: devem aparecer subentendidas na forma de falar.\n"
                "- O resultado deve soar como diálogo real, não narrativa.\n"
                "- Não invente fatos sobre temas que o NPC não saberia.\n"
                "- Quando não souber, diga que não sabe de forma natural e compatível com a persona, sem oferecer ajuda ou soluções genéricas.\n"
                "\n"
                "HUMANIZAÇÃO E NATURALIDADE:\n"
                "- Priorize naturalidade sobre fidelidade literal.\n"
                "- Pode incluir expressões humanas leves: suspiros implícitos, engasgos, sarcasmo, ironia, pausas reflexivas.\n"
                "- A fala deve ter cadência humana: começos hesitantes, reformulações breves e expressões espontâneas.\n"
                "- Remova rigidez textual e transforme em voz viva.\n"
                "\n"
                "QUANDO EDITAR:\n"
                "- SOMENTE edite se a fala precisar soar mais natural.\n"
                "- Se já estiver excelente para ser falada, mantenha quase igual.\n"
                "- Ajuste apenas ritmo, fluidez, naturalidade e conversação.\n"
                "- Evite reescritas completas; foque em melhorias pontuais.\n"
                "\n"
                "FORMATO DE SAÍDA:\n"
                "- Se fizer alterações, retorne um JSON:\n"
                "  {\n"
                "    \"fala\": \"<fala final otimizada>\",\n"
                "    \"justificativa\": \"<explicação breve do motivo da alteração>\"\n"
                "  }\n"
                "- Se não fizer alterações, retorne apenas a fala final como texto simples.\n"
                "- Sem aspas extras, sem markdown.\n"
                "- A fala deve estar pronta para ser dita em voz alta, de forma humana e natural."
            )

        ),
        HumanMessage(
            content=(
                "CONTEXTO COMPLETO DO NPC:\n"
                f"INTENÇÃO: {intent or '(nenhuma)'}\n"
                f"EMOÇÕES ATUAIS: {emotions}\n"
                f"PLANO: {plan or '(nenhum)'}\n"
                f"OBJETIVO IMEDIATO: {current_goal or '(nenhum)'}\n"
                f"CONTEXTO PERCEBIDO: {perceived_context or '(nenhum)'}\n"
                f"PISTAS AMBIENTAIS: {environmental_cues or '(nenhuma)'}\n"
                f"\n"
                f"ANÁLISE DE PERSONALIDADE: {personality_analysis or '(nenhuma)'}\n"
                f"ESTADO EMOCIONAL: {emotional_state or emotions}\n"
                f"MEMÓRIAS RELEVANTES: {relevant_memories or '(nenhuma)'}\n"
                f"CONHECIMENTO DE MUNDO: {world_knowledge or '(nenhum)'}\n"
                f"\n"
                f"{relationship_info}"
                f"\n"
                f"TRECHOS DE LORE: {lore or '(nenhum)'}\n"
                f"\n"
                f"RESPOSTA PROPOSTA DO NPC (avaliar e editar apenas se necessário, considerando TODAS as informações acima):\n"
                f"{reply}"
            )
        ),
    ]

    _logger.info(
        "critic.in: has_reply=%s lore_len=%s intent=%s emotions=%s has_personality=%s has_relationship=%s",
        bool(reply),
        len(str(lore)),
        intent,
        emotions,
        bool(personality_analysis),
        bool(relationship_info),
    )

    text = await _llm.run(prompt)
    text = (text or "").strip()

    # Log do texto bruto recebido (apenas para debug)
    _logger.debug("critic.raw_response: %s", text[:200] + "..." if len(text) > 200 else text)

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
            # Remove "json" se estiver no início do code block
            if text.lower().startswith("json"):
                text = text[4:].strip()

        # Tenta encontrar JSON no texto (pode vir junto com texto antes)
        # Procura por um objeto JSON válido no texto
        json_start = text.find("{")
        json_end = text.rfind("}")

        if json_start >= 0 and json_end > json_start:
            # Extrai o JSON
            json_text = text[json_start:json_end + 1]
            try:
                parsed = json.loads(json_text)
                if isinstance(parsed, dict):
                    final = parsed.get("fala", "").strip().strip('"').strip("'")
                    justificativa = parsed.get("justificativa", "").strip()
                    # IMPORTANTE: Se encontrou JSON válido, usa APENAS a fala extraída do JSON
                    # Ignora qualquer texto antes do JSON (que pode ser a fala repetida)
                else:
                    # Se não for dict, usa o texto antes do JSON (se houver)
                    if json_start > 0:
                        final = text[:json_start].strip().strip('"').strip("'")
                    else:
                        final = text.strip().strip('"').strip("'")
            except json.JSONDecodeError:
                # Se o JSON não for válido, tenta parsear o texto inteiro
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        final = parsed.get("fala", "").strip().strip('"').strip("'")
                        justificativa = parsed.get("justificativa", "").strip()
                    else:
                        final = text.strip().strip('"').strip("'")
                except json.JSONDecodeError:
                    # Se não conseguir parsear, usa o texto antes do JSON (se houver)
                    if json_start > 0:
                        final = text[:json_start].strip().strip('"').strip("'")
                    else:
                        final = text.strip().strip('"').strip("'")
        else:
            # Não encontrou JSON, tenta parsear o texto inteiro
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    final = parsed.get("fala", "").strip().strip('"').strip("'")
                    justificativa = parsed.get("justificativa", "").strip()
                else:
                    final = text.strip().strip('"').strip("'")
            except json.JSONDecodeError:
                # Se não for JSON válido, trata como texto simples (sem alterações)
                final = text.strip().strip('"').strip("'")
    except Exception as e:
        # Em caso de qualquer erro, usa o texto como está
        _logger.warning(f"critic.parse_error: {e}, usando texto completo como fala")
        final = text.strip().strip('"').strip("'")

    _logger.info("critic.out: %s\n", final)
    if justificativa:
        _logger.info("critic.justificativa: %s\n", justificativa)

    # Garante que final não contenha justificativa ou JSON
    # Remove qualquer JSON que possa ter ficado no final
    if final and "{" in final:
        # Se ainda contém JSON, tenta extrair apenas a parte antes do JSON
        json_pos = final.find("{")
        if json_pos > 0:
            final = final[:json_pos].strip()
        else:
            # Se o JSON está no início, tenta extrair do JSON
            json_end = final.find("}")
            if json_end > 0:
                try:
                    json_text = final[:json_end + 1]
                    parsed = json.loads(json_text)
                    if isinstance(parsed, dict) and "fala" in parsed:
                        final = parsed.get("fala", "").strip().strip('"').strip("'")
                except json.JSONDecodeError:
                    pass

    # Comparação: candidate vs final
    _logger.info("COMPARAÇÃO:\n")
    _logger.info("dialogue.candidate: %s", reply)
    _logger.info("critic.final: %s\n", final)

    # fala final no scratch (já limpa, sem JSON ou justificativa)
    state["scratch"]["final_reply"] = final

    # gera áudio em memória (não salva em disco) - APENAS a fala limpa
    audio_bytes = None
    try:
        npc_id = state.get("npc_id")
        audio_bytes = synthesize_npc_voice_bytes(final, persona, npc_id=npc_id)
    except Exception as e:
        _logger.exception("critic.tts_error: %s", e)

    # ação final para o runtime - APENAS a fala, sem justificativa
    action = {
        "type": "say",
        "content": final,
    }
    if audio_bytes is not None:
        # o engine do jogo decide como usar esses bytes (stream, websocket, etc.)
        action["audio"] = audio_bytes

    state["action"] = action
    return state
