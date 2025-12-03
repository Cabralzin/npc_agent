import uuid
import logging
import json
import os
from typing import Optional, Dict, Any, List
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from core.state import NPCState
from graph.wiring import build_graph
from graph.prompts import sys_persona
from core.persona import Persona, DEFAULT_PERSONA
from core.memory import EpisodicMemory
from tools import TOOLS_REGISTRY
from core.json_memory import JSONMemoryStore, CategorizedMemoryStore
from core.llm import LLMHarness

class NPCGraph:
    def __init__(self, persona: Persona = DEFAULT_PERSONA, npc_id: Optional[str] = None):
        # Configure logger
        self.logger = logging.getLogger("npc.runtime")
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
        self.persona = persona
        self.npc_id = npc_id or persona.name
        self.store = JSONMemoryStore(self.npc_id)
        self.kb = CategorizedMemoryStore(self.npc_id)
        self.memory = MemorySaver()
        # Initialize the graph with the checkpointer
        graph = build_graph()
        self.app = graph.compile(checkpointer=self.memory)

    def _seed(self) -> Dict[str, Any]:
        return {
            "npc_id": self.npc_id,
            "messages": [sys_persona(self.persona), self._kb_system_message()],
            "events": [],
            "intent": None,
            "emotions": {},
            "scratch": {},
            "action": None,
            "persona": self.persona
        }

    def _kb_system_message(self, max_items_per_cat: int = 5, max_summary_len: int = 140) -> SystemMessage:
        """Constrói uma SystemMessage concisa com fatos do KB categorizado."""
        try:
            data = self.kb.read()
        except Exception:
            data = {}
        lines: List[str] = [
            "Memórias conhecidas do NPC (resumo; use como contexto e mantenha consistência).",
        ]
        order = ("life", "people", "places", "skills", "objects")
        labels = {
            "life": "Vida",
            "people": "Pessoas",
            "places": "Lugares/Rotas",
            "skills": "Habilidades",
            "objects": "Objetos",
        }
        for cat in order:
            items = data.get(cat, []) if isinstance(data, dict) else []
            if not items:
                continue
            lines.append(f"{labels.get(cat, cat).upper()}:")
            for it in items[:max_items_per_cat]:
                title = str(it.get("title", "")).strip()
                summ = str(it.get("summary", "")).strip()
                if max_summary_len and len(summ) > max_summary_len:
                    summ = summ[: max_summary_len - 1] + "…"
                if title and summ:
                    lines.append(f"- {title}: {summ}")
        content = "\n".join(lines)
        return SystemMessage(content=content)

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
        
        # Pre-memorize so o KB já influencie este mesmo turno
        try:
            await self._auto_memorize(user_text=user_text, reply_text="", events=events or [], messages=state.get("messages", []))
            # Atualiza a SystemMessage de KB inserida no seed
            msgs = state.get("messages", [])
            if len(msgs) >= 2 and isinstance(msgs[1], SystemMessage):
                msgs[1] = self._kb_system_message()
                state["messages"] = msgs
        except Exception as e:
            self.logger.warning(f"[tid={tid}] pre_auto_memorize failed: {e}")
            
        # Ensure all required keys are present
        for key in ["intent", "emotions", "scratch", "action", "persona"]:
            if key not in state:
                state[key] = None if key == "intent" or key == "action" else {}
                
        # Invoke the graph
        result = await self.app.ainvoke(state, config=config)
        scratch = result.get("scratch", {}) or {}
        
        # Prepara action para log (remove áudio binário se existir)
        action_for_log = result.get("action")
        if action_for_log and isinstance(action_for_log, dict):
            action_for_log = dict(action_for_log)
            if "audio" in action_for_log:
                action_for_log["audio"] = f"<bytes: {len(action_for_log['audio'])} bytes>"
        
        self.logger.info(
            f"[tid={tid}] graph executed; intent={result.get('intent')} "
            f"scratch_keys={list(scratch.keys())} "
            f"action={action_for_log} "
            f"final_reply={scratch.get('final_reply')}"
        )

        action = result.get("action")
        reply_text = None
        
        if action and action.get("type") == "tool":
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
            # Tenta pegar do action primeiro (definido pelo critic)
            if action and isinstance(action, dict) and action.get("content"):
                reply_text = action.get("content")
            
            # Se não encontrou no action, tenta do scratch como fallback
            if not reply_text:
                fallback = scratch.get("final_reply") or scratch.get("candidate_reply")
                if fallback:
                    reply_text = fallback
                    # Garante que o action tenha o conteúdo correto
                    if not action or not isinstance(action, dict):
                        action = {"type": "say", "content": fallback}
                    else:
                        action["content"] = fallback
                        action["type"] = "say"
                else:
                    # Se ainda não encontrou, cria action vazio para não quebrar
                    action = action or {"type": "say", "content": ""}

        self.logger.info(f"[tid={tid}] reply={reply_text}")

        # Persist minimal, readable memory per interaction
        try:
            # Não tentar serializar bytes de áudio no JSON de memória
            action_for_store = dict(action) if isinstance(action, dict) else action
            if isinstance(action_for_store, dict):
                action_for_store.pop("audio", None)

            record = self.store.minimal_record(
                user_text=user_text,
                reply_text=reply_text,
                intent=result.get("intent"),
                action=action_for_store,
                events=events,
                extras={"thread_id": tid},
            )
            self.store.append(record)
        except Exception:
            pass

        # Auto-build categorized KB from the latest turn
        try:
            await self._auto_memorize(user_text=user_text, reply_text=reply_text or "", events=events or [], messages=result.get("messages", []))
        except Exception as e:
            self.logger.warning(f"[tid={tid}] auto_memorize failed: {e}")

        # Reduz mensagens para manter apenas as últimas N (EpisodicMemory)
        # Nota: O LangGraph já salva o estado automaticamente no checkpoint após ainvoke,
        # então não precisamos executar o grafo novamente apenas para salvar o estado reduzido
        # result["messages"] = EpisodicMemory().reduce(result.get("messages", []))
        # await self.app.ainvoke(result, config={"configurable": {"thread_id": tid}})
        
        return {
            "thread_id": tid,
            "action": action,
            "reply_text": reply_text,
            "audio": action.get("audio") if isinstance(action, dict) else None,
        }

    async def _auto_memorize(self, *, user_text: str, reply_text: str, events: List[Dict[str, Any]], messages: List[Any]) -> None:
        """Usa LLM para detectar NOVAS ou ATUALIZADAS memórias e persistir no KB.

        Saída esperada do LLM: JSON com chaves life, people, places, skills, objects.
        Cada chave: lista de {title, summary, metadata?}. Só incluir itens novos ou que precisam atualizar.
        """
        # Seleciona apenas o trecho final da conversa para contexto
        recent_msgs = messages[-8:] if isinstance(messages, list) else []
        # Snapshot do KB atual
        try:
            kb_snapshot = self.kb.read()
        except Exception:
            kb_snapshot = {"life": [], "people": [], "places": [], "skills": [], "objects": []}

        # Constrói prompt instruindo comparação com o KB atual e JSON estrito
        sys = {
            "role": "system",
            "content": (
                "Tarefa: Extraia memórias NOVAS ou ATUALIZADAS do diálogo recente, comparando com o KB atual do NPC.\n"
                "Fontes permitidas: APENAS o diálogo fornecido e o KB atual. Não utilize conhecimento externo.\n"
                "Categorias:\n"
                "- life: identidade, objetivos atuais, relações duráveis do NPC.\n"
                "- people: indivíduos ou grupos específicos identificáveis (nomes próprios).\n"
                "- places: locais físicos/rotas/estruturas com localização ou acesso plausível.\n"
                "- skills: capacidades que alguém afirma ter ou demonstra.\n"
                "- objects: itens/artefatos tangíveis com finalidade clara.\n"
                "Políticas anti-alucinação:\n"
                "- Somente escreva um item se houver evidência explícita no diálogo.\n"
                "- Não crie pessoas/lugares/objetos genéricos sem ancoragem clara (ex.: 'Efeitos colaterais' NÃO é lugar).\n"
                "- Se incerto, NÃO adicione. Prefira não escrever a inventar.\n"
                "- Você pode reformular/resumir, mas não inventar novos fatos.\n"
                "Regras de atualização:\n"
                "- Compare com o KB: se existir mesmo 'title', atualize 'summary' apenas se houver informação nova relevante.\n"
                "- 'title' deve ser curto e desambiguado (ex.: 'Sanimimarruchi', 'Ruínas do templo ao norte', 'Relíquia antiga').\n"
                "- 'summary' em 1–2 frases, incluindo atributos essenciais (ex.: profissão, relação, localização/rota, utilidade).\n"
                "- 'metadata' deve incluir {source: 'dialogue', confidence: 0.x, evidence: '<trecho curto citado>'}.\n"
                "Saída: UM JSON válido com chaves life/people/places/skills/objects.\n"
                "Se não houver nada novo/atualizável em uma categoria, retorne lista vazia nessa categoria.\n"
                "NÃO inclua comentários nem texto fora do JSON."
            ),
        }
        conv_payload: List[Dict[str, Any]] = [sys]
        # Anexa snapshot do KB como contexto
        conv_payload.append({"role": "system", "content": f"KB_ATUAL=\n{json.dumps(kb_snapshot, ensure_ascii=False)}"})
        # Inclui últimas mensagens como contexto bruto
        for m in recent_msgs:
            try:
                role = getattr(m, "type", None) or getattr(m, "role", None)
                content = getattr(m, "content", None)
                if not content:
                    continue
                if role == "human":
                    conv_payload.append({"role": "user", "content": str(content)})
                elif role == "ai":
                    conv_payload.append({"role": "assistant", "content": str(content)})
                elif role == "system":
                    conv_payload.append({"role": "system", "content": str(content)})
            except Exception:
                continue
        # Eventos perceptuais
        if events:
            ev_summary = "; ".join(f"[{e.get('source','GM')}] {e.get('type','info')}: {e.get('content','')}" for e in events)
            conv_payload.append({"role": "user", "content": f"Eventos recentes: {ev_summary}"})
        # Último par user/assistant explícito
        conv_payload.append({"role": "user", "content": user_text})
        if reply_text:
            conv_payload.append({"role": "assistant", "content": reply_text})

        # LLM obrigatório: não usar heurística
        data = None
        try:
            from core.models_preset import NPC_KB_MODEL
            harness = LLMHarness(model=NPC_KB_MODEL, temperature=0.2, max_retries=2, timeout=30)
            raw = await harness.run(conv_payload, agent_name="auto_memorize", npc_id=self.npc_id)
        except Exception as e:
            self.logger.warning(f"auto_memorize: LLM failed, skipping memorization this turn: {e}")
            return
        # Tenta extrair JSON limpo (remove cercas de código, se houver)
        txt = raw.strip()
        if txt.startswith("```"):
            # remove ```json ... ```
            first = txt.find("\n")
            last = txt.rfind("```")
            if first != -1 and last != -1:
                txt = txt[first+1:last].strip()
        try:
            data = json.loads(txt) if txt else None
        except Exception:
            data = None

        def iter_items(cat: str):
            items = data.get(cat, []) if isinstance(data, dict) else []
            if isinstance(items, list):
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    title = str(it.get("title", "")).strip()
                    summary = str(it.get("summary", "")).strip()
                    meta = it.get("metadata") if isinstance(it.get("metadata"), dict) else None
                    if title and summary:
                        yield title, summary, meta

        if not isinstance(data, dict):
            return
        for cat in ("life", "people", "places", "skills", "objects"):
            for title, summary, meta in iter_items(cat):
                try:
                    self.kb.upsert_item(category=cat, title=title, summary=summary, metadata=meta)
                    self.logger.info(f"auto_memorize: +KB [{cat}] '{title}'")
                except Exception:
                    continue
