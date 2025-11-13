from typing import Dict
from core.state import NPCState

async def perception(state: NPCState) -> NPCState:
    events = state.get("events", [])
    if not events:
        return state
    summary = "; ".join(
        f"[{e.get('source','GM')}] {e.get('type','info')}: {e.get('content','')}" for e in events
    )
    state["scratch"]["event_summary"] = summary
    state["events"] = []
    return state
