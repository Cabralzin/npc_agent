import logging
import json
import re
from typing import Dict, List, Any, Optional
from core.state import NPCState
from core.relationship_store import RelationshipStore
from core.llm import LLMHarness
from core.models_preset import REL_MODEL
from langchain_core.messages import SystemMessage, HumanMessage

_llm = LLMHarness(model=REL_MODEL)
_logger = logging.getLogger("npc.agents.relationship")

RELATIONSHIP_SYS_PROMPT = """
Você é o MÓDULO DE RELACIONAMENTOS de um NPC em um RPG de mesa.

OBJETIVO
- Analisar a interação atual e determinar seu impacto nos relacionamentos do NPC.
- Atualizar os valores de relacionamento (trust, fear, respect, attachment, hostility, dependance).
- Identificar se houve traição ou eventos significativos.
- Registrar a interação no histórico com seu impacto.

⚠️ IMPORTANTE: O "character_name" deve ser o NOME DA PESSOA QUE ESTÁ FALANDO COM O NPC, NÃO o nome do NPC.
- Se a mensagem começar com "Nome: mensagem", o nome é quem está falando.
- Se a mensagem começar com "Nome disse: mensagem", o nome é quem está falando.
- O character_name NUNCA deve ser o nome do NPC mencionado no prompt.

DIMENSÕES DE RELACIONAMENTO (valores de 0.0 a 1.0):
- trust (confiança): quanto o NPC confia no personagem
- fear (medo): quanto o NPC teme o personagem
- respect (respeito): quanto o NPC respeita o personagem
- attachment (apego): quanto o NPC se sente apegado ao personagem
- hostility (hostilidade): quanto o NPC é hostil ao personagem
- dependance (dependência): quanto o NPC depende do personagem
- betrayal_memory (memória de traição): descrição de traições passadas (vazio se não houver)

REGRAS
- Analise o tom, conteúdo e contexto da interação.
- Considere a personalidade do NPC ao avaliar o impacto.
- Ajustes devem ser graduais e coerentes com o histórico.
- Se houver traição ou quebra de confiança, atualize betrayal_memory.
- Valores devem estar entre 0.0 e 1.0.

FORMATO DE SAÍDA (JSON)
{
  "character_name": "<nome da PESSOA QUE FALOU com o NPC, NÃO o nome do NPC>",
  "updates": {
    "trust": 0.0-1.0 ou null (se não mudar),
    "fear": 0.0-1.0 ou null,
    "respect": 0.0-1.0 ou null,
    "attachment": 0.0-1.0 ou null,
    "hostility": 0.0-1.0 ou null,
    "dependance": 0.0-1.0 ou null,
    "betrayal_memory": "<texto>" ou null
  },
  "interaction_event": "<descrição breve do evento/interação>",
  "interaction_impact": {
    "trust": <mudança em trust, pode ser negativo>,
    "fear": <mudança em fear>,
    "respect": <mudança em respect>,
    "attachment": <mudança em attachment>,
    "hostility": <mudança em hostility>,
    "dependance": <mudança em dependance>
  }
}

Retorne APENAS o JSON, sem markdown, sem explicações adicionais.
"""


def extract_character_name(user_text: str, messages: List[Any], npc_name: str = "") -> Optional[str]:
    """Tenta extrair o nome do personagem que está falando (não o NPC) da mensagem do usuário."""
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
            # Ignora nomes muito curtos ou muito longos (provavelmente não são nomes)
            if 2 <= len(name) <= 30:
                return name
    
    # Se não encontrou padrão, tenta pegar a primeira palavra se for capitalizada
    words = user_text.strip().split()
    if words and words[0][0].isupper() and len(words[0]) >= 2:
        # Verifica se não é uma palavra comum no início
        common_starters = ["Eu", "Você", "Ele", "Ela", "Nós", "Eles", "Elas", "O", "A", "Os", "As", "Um", "Uma"]
        # Verifica se não é o nome do NPC
        if words[0] not in common_starters:
            if npc_name and words[0].lower() != npc_name.lower():
                return words[0]
            elif not npc_name:
                return words[0]
    
    return None


async def relationship(state: NPCState) -> NPCState:
    """Analisa e atualiza relacionamentos baseado na interação atual."""
    npc_id = state.get("npc_id", "")
    persona = state.get("persona")
    scratch = state.get("scratch", {})
    
    # Extrai a última mensagem do usuário
    last_user_message = next(
        (m for m in reversed(state.get("messages", [])) if isinstance(m, HumanMessage)),
        None
    )
    user_text = last_user_message.content if last_user_message else ""
    
    if not user_text:
        _logger.info("relationship.out: sem mensagem do usuário, pulando análise\n")
        return state
    
    # Obtém o nome do NPC para evitar confusão
    npc_name = persona.name if persona else ""
    
    # Tenta extrair o nome do personagem que está falando (NÃO o NPC)
    character_name = extract_character_name(user_text, state.get("messages", []), npc_name=npc_name)
    if not character_name:
        # Se não conseguiu extrair, usa um nome genérico
        character_name = "Jogador"  # Fallback padrão
    
    # Lê relacionamento atual
    relationship_store = RelationshipStore(npc_id)
    current_relationship = relationship_store.get_relationship(character_name)
    
    # Última resposta do NPC
    last_npc_reply = scratch.get("final_reply") or scratch.get("candidate_reply", "")
    
    # Contexto da interação
    event_summary = scratch.get("event_summary", "")
    intent = state.get("intent", "")
    emotions = state.get("emotions", {})
    
    _logger.info(
        "relationship.in: character_name=%s has_current_rel=%s",
        character_name,
        bool(current_relationship)
    )
    
    # Monta o prompt para análise
    prompt = [
        SystemMessage(content=RELATIONSHIP_SYS_PROMPT),
        HumanMessage(
            content=(
                f"PERSONA DO NPC:\n"
                f"Nome: {persona.name if persona else 'NPC'}\n"
                f"Backstory: {persona.backstory if persona and persona.backstory else 'N/A'}\n"
                f"Traits: {', '.join(persona.traits) if persona and persona.traits else 'N/A'}\n"
                f"\n"
                f"RELACIONAMENTO ATUAL COM {character_name}:\n"
                f"Trust: {current_relationship.get('trust', 0.5):.2f}\n"
                f"Fear: {current_relationship.get('fear', 0.0):.2f}\n"
                f"Respect: {current_relationship.get('respect', 0.5):.2f}\n"
                f"Attachment: {current_relationship.get('attachment', 0.0):.2f}\n"
                f"Hostility: {current_relationship.get('hostility', 0.0):.2f}\n"
                f"Dependance: {current_relationship.get('dependance', 0.0):.2f}\n"
                f"Betrayal Memory: {current_relationship.get('betrayal_memory', '') or '(nenhuma)'}\n"
                f"\n"
                f"INTERAÇÃO ATUAL:\n"
                f"PESSOA QUE FALOU (não o NPC): {user_text}\n"
                f"NPC ({persona.name if persona else 'NPC'}) respondeu: {last_npc_reply}\n"
                f"\n"
                f"⚠️ LEMBRE-SE: O 'character_name' no JSON deve ser o nome da PESSOA QUE FALOU, NÃO o nome do NPC ({persona.name if persona else 'NPC'}).\n"
                f"\n"
                f"CONTEXTO:\n"
                f"Eventos: {event_summary or '(nenhum)'}\n"
                f"Intenção do NPC: {intent or '(nenhuma)'}\n"
                f"Emoções do NPC: {', '.join(f'{k}:{v:.2f}' for k, v in emotions.items()) if emotions else '(nenhuma)'}\n"
                f"\n"
                f"Analise o impacto desta interação nos relacionamentos do NPC com a pessoa que falou e retorne o JSON conforme o formato especificado."
            )
        )
    ]
    
    try:
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
            # Extrai informações
            detected_name = parsed.get("character_name", character_name)
            
            # Validação: se o nome detectado for o nome do NPC, usa o nome extraído anteriormente
            if npc_name and detected_name.lower() == npc_name.lower():
                _logger.warning(
                    "relationship.out: LLM retornou nome do NPC (%s) em vez do nome da pessoa que fala, usando nome extraído: %s",
                    detected_name,
                    character_name
                )
                detected_name = character_name
            
            updates = parsed.get("updates", {})
            interaction_event = parsed.get("interaction_event", "")
            interaction_impact = parsed.get("interaction_impact", {})
            
            # Atualiza o relacionamento
            relationship_store.update_relationship(
                detected_name,
                trust=updates.get("trust"),
                fear=updates.get("fear"),
                respect=updates.get("respect"),
                attachment=updates.get("attachment"),
                hostility=updates.get("hostility"),
                dependance=updates.get("dependance"),
                betrayal_memory=updates.get("betrayal_memory"),
                interaction_event=interaction_event,
                interaction_impact=interaction_impact
            )
            
            # Lê o relacionamento atualizado para log
            updated_rel = relationship_store.get_relationship(detected_name)
            
            _logger.info(
                "relationship.out: character=%s trust=%.2f fear=%.2f respect=%.2f attachment=%.2f hostility=%.2f dependance=%.2f\n",
                detected_name,
                updated_rel.get("trust", 0.5),
                updated_rel.get("fear", 0.0),
                updated_rel.get("respect", 0.5),
                updated_rel.get("attachment", 0.0),
                updated_rel.get("hostility", 0.0),
                updated_rel.get("dependance", 0.0)
            )
            
            if interaction_event:
                _logger.info("relationship.interaction: event=%s impact=%s\n", interaction_event, interaction_impact)
        else:
            _logger.warning("relationship.out: resposta do LLM não é um dict válido\n")
            
    except json.JSONDecodeError as e:
        _logger.warning("relationship.out: erro ao parsear JSON: %s\n", e)
    except Exception as e:
        _logger.exception("relationship.out: erro ao processar relacionamento: %s\n", e)
    
    return state

