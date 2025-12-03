import logging
from core.state import NPCState
from core.json_memory import JSONMemoryStore
from core.llm import LLMHarness
from core.models_preset import EMOTION_MODEL
from langchain_core.messages import SystemMessage, HumanMessage

_llm = LLMHarness(model=EMOTION_MODEL)
_logger = logging.getLogger("npc.agents.dinamic_emotion")

DYNAMIC_EMOTION_SYS_PROMPT = """
Você é o MÓDULO DE EMOÇÕES DINÂMICAS de um NPC em um RPG de mesa.

OBJETIVO
- Analisar o histórico de interações do NPC e ajustar suas emoções de forma dinâmica, coerente.
- Considerar o contexto das conversas anteriores, a última interação e as emoções atuais.
- As emoções devem evoluir naturalmente baseadas nas experiências do NPC.

EMOÇÕES DISPONÍVEIS
- vigilância: nível de alerta e desconfiança (0.0 a 1.0)
- empatia: nível de compaixão e conexão emocional (0.0 a 1.0)
- confiança: nível de confiança no jogador/outros (0.0 a 1.0)
- medo: nível de medo ou ansiedade (0.0 a 1.0)
- raiva: nível de irritação ou hostilidade (0.0 a 1.0)
- alegria: nível de felicidade ou satisfação (0.0 a 1.0)
- tristeza: nível de melancolia ou desânimo (0.0 a 1.0)
- curiosidade: nível de interesse ou fascínio (0.0 a 1.0)

REGRAS
- As emoções devem ser ajustadas gradualmente, não de forma abrupta.
- Considere o tom e conteúdo das interações anteriores.
- Se o jogador foi amigável consistentemente, aumente confiança e empatia.
- Se houve ameaças ou traições, aumente vigilância e medo.
- Se houve momentos positivos, aumente alegria.
- Mantenha coerência com a personalidade do NPC.

FORMATO DE SAÍDA (JSON)
{
  "emotions": {
    "vigilância": 0.0-1.0,
    "empatia": 0.0-1.0,
    "confiança": 0.0-1.0,
    "medo": 0.0-1.0,
    "raiva": 0.0-1.0,
    "alegria": 0.0-1.0,
    "tristeza": 0.0-1.0,
    "curiosidade": 0.0-1.0
  },
  "justificativa": "breve explicação das mudanças emocionais"
}

Retorne APENAS o JSON, sem markdown, sem explicações adicionais.
"""


async def dinamic_emotion(state: NPCState) -> NPCState:
    """Ajusta as emoções do NPC dinamicamente baseado no histórico de interações."""
    npc_id = state.get("npc_id", "")
    current_emotions = state.get("emotions", {}) or {}
    persona = state.get("persona")
    scratch = state.get("scratch", {})
    
    # Lê mensagens históricas do JSON
    memory_store = JSONMemoryStore(npc_id)
    historical_messages = memory_store._read()
    
    # Última interação do state atual
    last_user_message = next(
        (m for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)),
        None
    )
    last_interaction = {
        "user": last_user_message.content if last_user_message else "",
        "timestamp": "current"
    }
    
    # Emoções anteriores (pode ser do último registro do JSON se houver)
    previous_emotions = {}
    if historical_messages:
        # Tenta extrair emoções do último registro se existir
        last_record = historical_messages[-1]
        if "emotions" in last_record:
            previous_emotions = last_record["emotions"]
    
    # Prepara contexto histórico (últimas 5 interações)
    recent_interactions = historical_messages[-5:] if len(historical_messages) > 5 else historical_messages
    history_summary = "\n".join(
        f"[{rec.get('ts', 'N/A')}] User: {rec.get('user', '')} | NPC: {rec.get('reply', '')[:100]}"
        for rec in recent_interactions
    )
    
    _logger.info(
        "dinamic_emotion.in: npc_id=%s has_history=%s current_emotions=%s",
        npc_id,
        len(historical_messages),
        ", ".join(f"{k}:{v:.2f}" for k, v in current_emotions.items()) if current_emotions else "(none)"
    )
    
    # Se não há histórico suficiente, mantém emoções atuais
    if not historical_messages and not last_user_message:
        _logger.info("dinamic_emotion.out: sem histórico suficiente, mantendo emoções atuais\n")
        return state
    
    # Monta o prompt para o LLM
    prompt = [
        SystemMessage(content=DYNAMIC_EMOTION_SYS_PROMPT),
        HumanMessage(
            content=(
                f"PERSONA:\n"
                f"Nome: {persona.name if persona else 'NPC'}\n"
                f"Backstory: {persona.backstory if persona else 'N/A'}\n"
                f"Traits: {', '.join(persona.traits) if persona and persona.traits else 'N/A'}\n"
                f"\n"
                f"HISTÓRICO DE INTERAÇÕES (últimas 5):\n{history_summary}\n"
                f"\n"
                f"ÚLTIMA INTERAÇÃO:\n"
                f"User: {last_interaction['user']}\n"
                f"\n"
                f"EMOÇÕES ATUAIS:\n"
                f"{', '.join(f'{k}: {v:.2f}' for k, v in current_emotions.items()) if current_emotions else 'Nenhuma emoção definida'}\n"
                f"\n"
                f"EMOÇÕES ANTERIORES (último registro):\n"
                f"{', '.join(f'{k}: {v:.2f}' for k, v in previous_emotions.items()) if previous_emotions else 'Nenhuma emoção anterior registrada'}\n"
                f"\n"
                f"Com base nessas informações, ajuste as emoções do NPC de forma dinâmica e coerente."
            )
        )
    ]
    
    try:
        text = await _llm.run(prompt)
        
        # Tenta parsear JSON da resposta
        import json
        # Remove markdown code blocks se houver
        text_clean = text.strip()
        if text_clean.startswith("```"):
            first_newline = text_clean.find("\n")
            last_backtick = text_clean.rfind("```")
            if first_newline >= 0 and last_backtick >= 0:
                text_clean = text_clean[first_newline + 1:last_backtick].strip()
        
        parsed = json.loads(text_clean)
        if isinstance(parsed, dict) and "emotions" in parsed:
            new_emotions = parsed["emotions"]
            justificativa = parsed.get("justificativa", "")
            
            # Valida e normaliza valores de emoção (0.0 a 1.0)
            validated_emotions = {}
            for key, value in new_emotions.items():
                if isinstance(value, (int, float)):
                    validated_emotions[key] = max(0.0, min(1.0, float(value)))
            
            state["emotions"] = validated_emotions
            
            # Armazena justificativa no scratch para referência
            scratch["emotion_justification"] = justificativa
            state["scratch"] = scratch
            
            _logger.info(
                "dinamic_emotion.out: emotions=%s\n",
                ", ".join(f"{k}:{v:.2f}" for k, v in validated_emotions.items())
            )
            if justificativa:
                _logger.info("dinamic_emotion.justificativa: %s\n", justificativa)
        else:
            _logger.warning("dinamic_emotion.out: resposta do LLM não contém 'emotions', mantendo emoções atuais\n")
    except json.JSONDecodeError as e:
        _logger.warning("dinamic_emotion.out: erro ao parsear JSON: %s, mantendo emoções atuais\n", e)
    except Exception as e:
        _logger.exception("dinamic_emotion.out: erro ao processar emoções dinâmicas: %s\n", e)
    
    return state

