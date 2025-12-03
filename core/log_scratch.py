"""Função auxiliar para logar o estado do scratch de forma organizada"""
import logging
from typing import Dict, Any

_logger = logging.getLogger("npc.core.log_scratch")


def log_scratch(scratch: Dict[str, Any], agent_name: str, section: str = "Saída"):
    """Loga o estado atual do scratch de forma organizada"""
    _logger.info("\nSCRATCH - %s (%s):", section, agent_name)
    
    # Campos principais do scratch
    fields = [
        ("event_summary", "Event Summary"),
        ("world_query", "World Query"),
        ("lore_hits", "Lore Hits"),
        ("plan", "Plan"),
        ("current_goal", "Current Goal"),
        ("perceived_context", "Perceived Context"),
        ("environmental_cues", "Environmental Cues"),
        ("personality_analysis", "Personality Analysis"),
        ("emotional_state", "Emotional State"),
        ("relevant_memories", "Relevant Memories"),
        ("world_knowledge", "World Knowledge"),
        ("candidate_reply", "Candidate Reply"),
        ("critic_feedback", "Critic Feedback"),
        ("final_reply", "Final Reply"),
    ]
    
    has_content = False
    for key, label in fields:
        value = scratch.get(key)
        if value:
            has_content = True
            # Trunca valores muito longos
            str_value = str(value)
            if len(str_value) > 150:
                str_value = str_value[:147] + "..."
            _logger.info("  %s: %s", label, str_value)
    
    if not has_content:
        _logger.info("  (scratch vazio ou sem campos preenchidos)")
    _logger.info("")

