import uuid
import logging
from typing import Optional, Dict, Any, List
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from core.state import NPCState
from graph.wiring import build_graph
from graph.prompts import sys_persona
from core.persona import Persona, DEFAULT_PERSONA
from core.memory import EpisodicMemory
from tools import TOOLS_REGISTRY
from core.json_memory import JSONMemoryStore

class NPCGraph:
    def __init__(self, persona: Persona = DEFAULT_PERSONA, npc_id: Optional[str] = None):
        # Configure logger
        self.logger = logging.getLogger("npc.runtime")
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
        self.persona = persona
        self.npc_id = npc_id or persona.name
        self.store = JSONMemoryStore(self.npc_id)
        self.memory = MemorySaver()
        # Initialize the graph with the checkpointer
        graph = build_graph()
        self.app = graph.compile(checkpointer=self.memory)

    def _seed(self) -> Dict[str, Any]:
        return {
            "npc_id": self.npc_id,
            "messages": [sys_persona(self.persona)],
            "events": [],
            "intent": None,
            "emotions": {},
            "scratch": {},
            "action": None,
            "persona": self.persona
        }

    async def respond_once(self, user_text: str, *, thread_id: Optional[str] = None, events: Optional[List[Dict[str, Any]]] = None):
        base_tid = thread_id or str(uuid.uuid4())
        tid = f"{self.npc_id}:{base_tid}"
        config = {"configurable": {"thread_id": tid}}
        
        # Initialize state
        state = self._seed()
        
        self.logger.info(f"[tid={tid}] user: {user_text}")
        if events:
            self.logger.info(f"[tid={tid}] events: {len(events)}")
        
        # Add the user's message
        if "messages" not in state:
            state["messages"] = []
        state["messages"].append(HumanMessage(content=user_text))
        
        # Add any events
        if events:
            if "events" not in state:
                state["events"] = []
            state["events"].extend(events)
            
        # Ensure all required keys are present
        for key in ["intent", "emotions", "scratch", "action", "persona"]:
            if key not in state:
                state[key] = None if key == "intent" or key == "action" else {}
                
        # Invoke the graph
        result = await self.app.ainvoke(state, config=config)
        self.logger.info(f"[tid={tid}] graph executed; intent={result.get('intent')} scratch_keys={list((result.get('scratch') or {}).keys())}")

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
            if not reply_text:
                scratch = result.get("scratch", {}) or {}
                fallback = scratch.get("final_reply") or scratch.get("candidate_reply")
                if fallback:
                    reply_text = fallback
                    action = {"type": "say", "content": fallback}

        self.logger.info(f"[tid={tid}] action={action} reply={reply_text}")

        # Persist minimal, readable memory per interaction
        try:
            record = self.store.minimal_record(
                user_text=user_text,
                reply_text=reply_text,
                intent=result.get("intent"),
                action=action,
                events=events,
                extras={"thread_id": tid},
            )
            self.store.append(record)
        except Exception:
            pass

        result["messages"] = EpisodicMemory().reduce(result.get("messages", []))
        await self.app.ainvoke(result, config={"configurable": {"thread_id": tid}})
        return {"thread_id": tid, "action": action, "reply_text": reply_text}