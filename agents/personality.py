import logging
from core.state import NPCState

_logger = logging.getLogger("npc.agents.personality")

async def personality(state: NPCState) -> NPCState:
    emotions = state.get("emotions", {}) or {}
    summary = state["scratch"].get("event_summary", "")
    _logger.info("personality.in: has_summary=%s emotions=%s", bool(summary), ", ".join(f"{k}:{v:.2f}" for k,v in emotions.items()) or "(none)")
    if "ameaça" in summary.lower():
        emotions["vigilância"] = min(1.0, emotions.get("vigilância", 0.3) + 0.2)
    if "ajuda" in summary.lower():
        emotions["empatia"] = min(1.0, emotions.get("empatia", 0.2) + 0.2)
    state["emotions"] = emotions
    _logger.info("personality.out: emotions=%s", ", ".join(f"{k}:{v:.2f}" for k,v in emotions.items()) or "(none)")
    return state