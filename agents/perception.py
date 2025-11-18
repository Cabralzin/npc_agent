from typing import Dict
import logging
from core.state import NPCState

_logger = logging.getLogger("npc.agents.perception")

async def perception(state: NPCState) -> NPCState:
    events = state.get("events", [])
    _logger.info("perception.in: events=%s", len(events))
    if not events:
        return state
    summary = "; ".join(
        f"[{e.get('source','GM')}] {e.get('type','info')}: {e.get('content','')}" for e in events
    )
    state["scratch"]["event_summary"] = summary
    state["events"] = []
    _logger.info("perception.out: summary_len=%s", len(summary))
    return state
