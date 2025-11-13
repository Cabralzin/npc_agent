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
    g.add_node("world_model", world_model)
    g.add_node("planner", planner)
    g.add_node("dialogue", dialogue)
    g.add_node("critic", critic)
    g.set_entry_point("perception")
    g.add_edge("perception", "personality")
    g.add_edge("personality", "world_model")
    g.add_edge("world_model", "planner")
    g.add_edge("planner", "dialogue")
    g.add_edge("dialogue", "critic")
    g.add_edge("critic", END)
    return g