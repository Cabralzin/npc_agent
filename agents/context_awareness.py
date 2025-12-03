import logging
from typing import List, Any
from core.state import NPCState
from core.llm import LLMHarness
from core.models_preset import SCENE_MODEL
from core.memory import SemanticMemory
from core.world_lore import WORLD_LORE
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

_llm = LLMHarness(model=SCENE_MODEL)
_logger = logging.getLogger("npc.agents.context_awareness")

CONTEXT_AWARENESS_SYS_PROMPT = """
Você é o MÓDULO DE CONSCIÊNCIA CONTEXTUAL de um NPC em um RPG de mesa.

OBJETIVO
- Analisar o contexto situacional atual: o que está acontecendo AGORA na cena.
- Identificar detalhes ambientais físicos, sons e ameaças do local.
- Gerar um contexto percebido claro e conciso (até 3 frases).
- Identificar pistas ambientais relevantes (detalhes físicos, sons, ameaças).

DIFERENÇA ENTRE CONTEXTO PERCEBIDO E PISTAS AMBIENTAIS:
- perceived_context: O QUE está acontecendo na situação atual (até 3 frases). Foco na ação, diálogo, eventos imediatos.
- environmental_cues: COMO o ambiente está (detalhes físicos, sons, ameaças, condições do local). Foco nos sentidos e perigos.

REGRAS
- perceived_context deve ser sobre a SITUAÇÃO ATUAL, não sobre objetivos ou planos futuros.
- Foque no que está acontecendo AGORA, não no que o NPC quer fazer depois.
- environmental_cues deve descrever o que o NPC percebe com os sentidos: sons, cheiros, visões, ameaças visíveis.
- Seja específico e concreto, não genérico.
- Use informações do world_lore se relevante para o contexto atual.

FORMATO DE SAÍDA (JSON)
{
  "perceived_context": "<até 3 frases descrevendo o que está acontecendo AGORA na situação>",
  "environmental_cues": "<detalhes físicos, sons, ameaças, condições do local que o NPC percebe>",
  "needs_world": <true/false - se precisa acessar world_model para mais informações>,
  "world_query": "<query para world_model se needs_world for true, ou null>"
}

Retorne APENAS o JSON, sem markdown, sem explicações adicionais.
"""


def get_last_3_messages(messages: List[Any]) -> List[str]:
    """Extrai as últimas 3 mensagens relevantes (HumanMessage e AIMessage)."""
    relevant = []
    for msg in messages:
        if isinstance(msg, (HumanMessage, AIMessage)):
            content = msg.content if hasattr(msg, 'content') else str(msg)
            if content and content.strip():
                relevant.append(content)
    return relevant[-3:] if len(relevant) > 3 else relevant


async def context_awareness(state: NPCState) -> NPCState:
    """Analisa o contexto situacional atual e gera perceived_context e environmental_cues."""
    persona = state.get("persona")
    scratch = state.get("scratch", {})
    
    # Sumário dos eventos
    event_summary = scratch.get("event_summary", "")
    
    # Últimas 3 falas
    messages = state.get("messages", [])
    last_3_messages = get_last_3_messages(messages)
    
    # Contexto adicional (emoções, intenções anteriores se houver)
    emotions = state.get("emotions", {})
    
    _logger.info(
        "context_awareness.in: has_events=%s last_messages=%s",
        bool(event_summary),
        len(last_3_messages)
    )
    
    # Busca informações do world_lore se houver eventos ou contexto relevante
    world_lore_info = ""
    if event_summary or last_3_messages:
        # Cria uma query baseada nos eventos e nas últimas mensagens
        query_parts = []
        if event_summary:
            query_parts.append(event_summary)
        if last_3_messages:
            # Extrai palavras-chave das últimas mensagens
            combined_text = " ".join(last_3_messages)
            query_parts.append(combined_text[:200])  # Limita para não ficar muito longo
        
        if query_parts:
            query = " ".join(query_parts)
            mem = SemanticMemory(lore_docs=WORLD_LORE)
            hits = mem.search(query, k=3)
            if hits:
                world_lore_info = "\n---\n".join(hits)
                _logger.info("context_awareness.world_lore: encontrou %d informações relevantes", len(hits))
    
    # Monta o prompt
    last_messages_text = "\n".join(
        f"[Mensagem {i+1}]: {msg}" for i, msg in enumerate(last_3_messages)
    ) if last_3_messages else "(nenhuma mensagem recente)"
    
    prompt = [
        SystemMessage(content=CONTEXT_AWARENESS_SYS_PROMPT),
        HumanMessage(
            content=(
                f"PERSONA DO NPC:\n"
                f"Nome: {persona.name if persona else 'NPC'}\n"
                f"Backstory: {persona.backstory if persona and persona.backstory else 'N/A'}\n"
                f"Traits: {', '.join(persona.traits) if persona and persona.traits else 'N/A'}\n"
                f"\n"
                f"EVENTOS PERCEBIDOS:\n{event_summary or '(nenhum evento)'}\n"
                f"\n"
                f"ÚLTIMAS 3 MENSAGENS DA CONVERSA:\n{last_messages_text}\n"
                f"\n"
                f"EMOÇÕES ATUAIS DO NPC:\n"
                f"{', '.join(f'{k}:{v:.2f}' for k, v in emotions.items()) if emotions else '(nenhuma emoção definida)'}\n"
                f"\n"
                f"INFORMAÇÕES DO MUNDO (se relevante):\n{world_lore_info or '(nenhuma informação específica do mundo)'}\n"
                f"\n"
                f"Com base nessas informações, analise o contexto situacional ATUAL e gere:\n"
                f"1. perceived_context: O que está acontecendo AGORA na situação (até 3 frases, foco na ação/diálogo atual)\n"
                f"2. environmental_cues: Detalhes físicos, sons, ameaças, condições do local que o NPC percebe\n"
                f"\n"
                f"⚠️ IMPORTANTE: perceived_context deve ser sobre o que está ACONTECENDO AGORA, não sobre objetivos ou planos futuros."
            )
        )
    ]
    
    try:
        import json
        text = await _llm.run(prompt)
        
        # Limpa o texto (remove markdown se houver)
        text_clean = text.strip()
        if text_clean.startswith("```"):
            first_newline = text_clean.find("\n")
            last_backtick = text_clean.rfind("```")
            if first_newline >= 0 and last_backtick >= 0:
                text_clean = text_clean[first_newline + 1:last_backtick].strip()
        # Remove "json" se estiver no início do code block
        if text_clean.lower().startswith("json"):
            text_clean = text_clean[4:].strip()
        
        parsed = json.loads(text_clean)
        
        if isinstance(parsed, dict):
            perceived_context = parsed.get("perceived_context", "")
            environmental_cues = parsed.get("environmental_cues", "")
            needs_world = parsed.get("needs_world", False)
            world_query = parsed.get("world_query", "")

            # Armazena no state
            state["perceived_context"] = perceived_context
            state["environmental_cues"] = environmental_cues

            # Também armazena no scratch para compatibilidade
            scratch["perceived_context"] = perceived_context
            scratch["environmental_cues"] = environmental_cues

            # Se precisar acessar world_model, define o flag e para onde retornar (retorna para si mesmo)
            if needs_world:
                scratch["needs_world"] = True
                scratch["world_model_return_to"] = "context_awareness"
                if world_query:
                    scratch["world_query"] = world_query
            else:
                # Limpa os flags se não precisar mais
                scratch.pop("needs_world", None)
                scratch.pop("world_query", None)
                scratch.pop("world_model_return_to", None)

            state["scratch"] = scratch
            
            _logger.info(
                "context_awareness.out: perceived_context=%s environmental_cues_len=%s\n",
                perceived_context[:100] + "..." if len(perceived_context) > 100 else perceived_context,
                len(environmental_cues)
            )
            if environmental_cues:
                _logger.info("context_awareness.environmental_cues: %s\n", environmental_cues[:150] + "..." if len(environmental_cues) > 150 else environmental_cues)
        else:
            _logger.warning("context_awareness.out: resposta do LLM não é um dict válido\n")
            
    except json.JSONDecodeError as e:
        _logger.warning("context_awareness.out: erro ao parsear JSON: %s\n", e)
        # Fallback: cria valores vazios
        state["perceived_context"] = ""
        state["environmental_cues"] = ""
        scratch["perceived_context"] = ""
        scratch["environmental_cues"] = ""
        state["scratch"] = scratch
    except Exception as e:
        _logger.exception("context_awareness.out: erro ao processar contexto: %s\n", e)
        # Fallback: cria valores vazios
        state["perceived_context"] = ""
        state["environmental_cues"] = ""
        scratch["perceived_context"] = ""
        scratch["environmental_cues"] = ""
        state["scratch"] = scratch
    
    return state

