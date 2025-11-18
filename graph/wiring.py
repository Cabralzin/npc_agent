from langgraph.graph import StateGraph, END
from core.state import NPCState
from agents.perception import perception
from agents.personality import personality
from agents.world_model import world_model
from agents.planner import planner
from agents.dialogue import dialogue
from agents.critic import critic

def build_graph() -> StateGraph[NPCState]:
    g = StateGraph(NPCState)
    g.add_node("perception", perception)
    g.add_node("personality", personality)
    g.add_node("planner", planner)
    g.add_node("world_model", world_model)
    g.add_node("dialogue", dialogue)
    g.add_node("critic", critic)
    g.set_entry_point("perception")
    g.add_edge("perception", "personality")
    g.add_edge("personality", "planner")

    def needs_world(state: NPCState) -> str:
        try:
            return "world_model" if bool((state.get("scratch") or {}).get("needs_world")) else "dialogue"
        except Exception:
            return "dialogue"

    g.add_conditional_edges("planner", needs_world, {
        "world_model": "world_model",
        "dialogue": "dialogue",
    })
    g.add_edge("world_model", "dialogue")
    g.add_edge("dialogue", "critic")
    g.add_edge("critic", END)
    return g