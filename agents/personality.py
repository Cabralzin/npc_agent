from core.state import NPCState

async def personality(state: NPCState) -> NPCState:
    emotions = state.get("emotions", {}) or {}
    summary = state["scratch"].get("event_summary", "")
    if "ameaça" in summary.lower():
        emotions["vigilância"] = min(1.0, emotions.get("vigilância", 0.3) + 0.2)
    if "ajuda" in summary.lower():
        emotions["empatia"] = min(1.0, emotions.get("empatia", 0.2) + 0.2)
    state["emotions"] = emotions
    return state