import uuid
from typing import Optional, Dict, Any, List
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from core.state import NPCState
from graph.wiring import build_graph
from graph.prompts import sys_persona
from core.persona import Persona, DEFAULT_PERSONA
from core.memory import EpisodicMemory
from tools import TOOLS_REGISTRY

class NPCGraph:
    def __init__(self, persona: Persona = DEFAULT_PERSONA):
        self.persona = persona
        self.memory = MemorySaver()
        self.app = build_graph().compile(checkpointer=self.memory)

    def _seed(self) -> NPCState:
        return NPCState(
            messages=[sys_persona(self.persona)],
            events=[], intent=None, emotions={}, scratch={},
            action=None, persona=self.persona
        )

    async def respond_once(self, user_text: str, *, thread_id: Optional[str] = None, events: Optional[List[Dict[str, Any]]] = None):
        tid = thread_id or str(uuid.uuid4())
        state_handle = await self.app.aget_state(tid)
        state = state_handle.values if state_handle else self._seed()
        state["messages"].append(HumanMessage(content=user_text))
        if events: state["events"].extend(events)
        result = await self.app.ainvoke(state, config={"configurable": {"thread_id": tid}})

        action = result.get("action") or {}
        reply_text = None
        if action.get("type") == "tool":
            tool = TOOLS_REGISTRY.get(action.get("name"))
            say = action.get("fallback_say", "")
            if tool:
                tool_out = tool.invoke(action.get("args", {}))
                result["messages"].append(AIMessage(content=f"[TOOL {action['name']}] {tool_out}"))
                result["messages"].append(AIMessage(content=say))
                action = {"type": "say", "content": say, "tool_result": str(tool_out)}
                reply_text = say
            else:
                action = {"type": "say", "content": say or "(falha de ferramenta)"}
                reply_text = action["content"]
        else:
            reply_text = (action or {}).get("content")

        result["messages"] = EpisodicMemory().reduce(result.get("messages", []))
        await self.app.ainvoke(result, config={"configurable": {"thread_id": tid}})
        return {"thread_id": tid, "action": action, "reply_text": reply_text}