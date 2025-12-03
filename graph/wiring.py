from langgraph.graph import StateGraph, END
from core.state import NPCState
from agents.perception import perception
from agents.personality import personality
from agents.dinamic_emotion import dinamic_emotion
from agents.context_awareness import context_awareness
from agents.world_model import world_model
from agents.planner import planner
from agents.dialogue import dialogue
from agents.critic import critic
from agents.relationship import relationship


def build_graph() -> StateGraph[NPCState]:
    g = StateGraph(NPCState)
    g.add_node("perception", perception)
    g.add_node("personality", personality)
    g.add_node("dinamic_emotion", dinamic_emotion)
    g.add_node("context_awareness", context_awareness)
    g.add_node("planner", planner)
    g.add_node("world_model", world_model)
    g.add_node("dialogue", dialogue)
    g.add_node("critic", critic)
    g.add_node("relationship", relationship)
    g.set_entry_point("perception")
    g.add_edge("perception", "personality")
    g.add_edge("personality", "dinamic_emotion")
    g.add_edge("dinamic_emotion", "context_awareness")

    def needs_world(state: NPCState) -> str:
        """Verifica se precisa acessar world_model."""
        try:
            scratch = state.get("scratch", {})
            # Se já retornou do world_model, limpa o flag e segue para o próximo
            if scratch.get("_returned_from_world_model"):
                scratch.pop("_returned_from_world_model", None)
                scratch.pop("needs_world", None)
                scratch.pop("world_query", None)
                state["scratch"] = scratch
                return "next"
            # Se precisa acessar world_model, vai para world_model
            if bool(scratch.get("needs_world")):
                return "world_model"
            return "next"
        except Exception:
            return "next"

    def world_model_return(state: NPCState) -> str:
        """Retorna do world_model para o agente que chamou."""
        try:
            scratch = state.get("scratch", {})
            return_to = scratch.get("world_model_return_to", "planner")
            # Marca que o agente deve processar novamente após retornar do world_model
            scratch["_returned_from_world_model"] = True
            # Mantém o world_model_return_to para saber para onde retornar
            state["scratch"] = scratch
            return return_to
        except Exception:
            return "planner"

    # context_awareness pode acessar world_model se necessário
    g.add_conditional_edges("context_awareness", needs_world, {
        "world_model": "world_model",
        "next": "planner",
    })

    # planner pode acessar world_model se necessário
    g.add_conditional_edges("planner", needs_world, {
        "world_model": "world_model",
        "next": "dialogue",
    })

    # dialogue não acessa world_model, usa apenas dados já presentes no state
    g.add_edge("dialogue", "critic")

    # world_model retorna para o agente que chamou (NUNCA para critic ou dialogue)
    g.add_conditional_edges("world_model", world_model_return, {
        "context_awareness": "context_awareness",
        "planner": "planner",
    })
    g.add_edge("critic", "relationship")
    g.add_edge("relationship", END)
    return g
