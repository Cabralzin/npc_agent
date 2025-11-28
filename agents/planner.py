from langchain_core.messages import SystemMessage, HumanMessage
import logging
from core.llm import LLMHarness
from core.state import NPCState
from graph.prompts import sys_persona

_llm = LLMHarness()
_logger = logging.getLogger("npc.agents.planner")


async def planner(state: NPCState) -> NPCState:
    persona = state["persona"]
    scratch = state.get("scratch", {}) or {}

    lore = scratch.get("lore_hits", "") or ""
    event_summary = scratch.get("event_summary", "(n/a)")
    emotions_dict = state.get("emotions", {}) or {}
    emotions = ", ".join(f"{k}:{v:.2f}" for k, v in emotions_dict.items()) or "neutro"

    # Contexto opcional vindo de nós anteriores ou execuções passadas
    last_user = scratch.get("last_user_message", "")
    last_npc = scratch.get("last_npc_reply", "")
    world_result = scratch.get("world_result", "")  # se já houve uma consulta em outro turno
    context_tags = scratch.get("context_tags", "")

    extra_ctx_lines = []
    if last_user:
        extra_ctx_lines.append(f"Última fala do jogador: {last_user}")
    if last_npc:
        extra_ctx_lines.append(f"Última fala do NPC: {last_npc}")
    if context_tags:
        extra_ctx_lines.append(f"Tags de contexto: {context_tags}")
    if world_result:
        extra_ctx_lines.append(f"Resultado recente do mundo (de consultas anteriores): {world_result}")

    extra_ctx = "\n".join(extra_ctx_lines) if extra_ctx_lines else "(sem contexto extra relevante)"

    prompt = [
        sys_persona(persona),
        SystemMessage(
            content=(
                "Você é o Planejador Interno do NPC. O fluxo do sistema é:\n"
                "- Primeiro: percepção e personalidade já foram processadas.\n"
                "- Agora: você planeja a intenção e o estado mental do NPC.\n"
                "- Em seguida: SE você marcar NEEDS_WORLD = yes, o próximo passo será um agente de mundo "
                "(world_model) respondendo à sua WORLD_QUERY.\n"
                "- Caso contrário, o fluxo irá direto para o agente de diálogo.\n"
                "\n"
                "TAREFA:\n"
                "- Definir uma INTENÇÃO de alto nível (o que o NPC quer fazer/comunicar AGORA).\n"
                "- Dizer se precisa ou não de mais informações do mundo antes de falar (NEEDS_WORLD).\n"
                "- Se precisar, montar uma WORLD_QUERY objetiva para o agente de mundo.\n"
                "- Preencher um quadro mental curto com: plano, objetivo atual, contexto percebido, pistas ambientais, "
                "como a personalidade pesa na reação, estado emocional, memórias relevantes e conhecimento de mundo "
                "que o NPC JÁ tem até aqui.\n"
                "\n"
                "REGRAS IMPORTANTES:\n"
                "- Cada campo deve ter 1 ou 2 frases, no máximo; seja funcional e direto.\n"
                "- Se marcar NEEDS_WORLD = yes, a WORLD_QUERY deve ser específica e prática, algo que o agente de mundo "
                "possa realmente responder (ex.: posição de ameaças, recursos próximos, estado de um local, etc.).\n"
                "- NÃO antecipe o resultado da WORLD_QUERY: o que virá depois será colocado em world_result "
                "e usado pelo diálogo em outro momento.\n"
                "- O campo WORLD_KNOWLEDGE deve descrever apenas o que o NPC já sabe antes de qualquer nova consulta.\n"
                "- Use emoções e lore só para deixar o planejamento coerente, sem exagerar.\n"
                "- Se não tiver informação suficiente para algum campo, preencha com algo genérico mas útil.\n"
                "\n"
                "FORMATO DE SAÍDA (exatamente essas linhas, sem comentários extra):\n"
                "INTENÇÃO: <texto curto>\n"
                "NEEDS_WORLD: <yes|no>\n"
                "WORLD_QUERY: <consulta ou vazio>\n"
                "PLAN: <plano de alto nível do NPC>\n"
                "CURRENT_GOAL: <objetivo imediato na cena>\n"
                "PERCEIVED_CONTEXT: <como o NPC enxerga a situação agora>\n"
                "ENVIRONMENTAL_CUES: <pistas do ambiente que o NPC percebe>\n"
                "PERSONALITY_ANALYSIS: <como a personalidade influencia sua reação>\n"
                "EMOTIONAL_STATE: <descrição curta do estado emocional>\n"
                "RELEVANT_MEMORIES: <memórias ou experiências que afetam a decisão>\n"
                "WORLD_KNOWLEDGE: <fatos do mundo que o NPC traz para o momento>"
            )
        ),
        HumanMessage(content=f"EVENTOS: {event_summary}"),
        HumanMessage(content=f"EMOÇÕES: {emotions}"),
        HumanMessage(content=f"LORE:\n{lore}"),
        HumanMessage(content=f"OUTROS DADOS INTERNOS (SCRATCH):\n{extra_ctx}"),
    ]

    _logger.info("planner.in: emotions=%s has_lore=%s", emotions, bool(lore))

    text = await _llm.run(prompt)
    raw = (text or "").strip()

    intent = None
    needs_world = False
    world_query = ""

    # Novos campos de estado mental
    plan = ""
    current_goal = ""
    perceived_context = ""
    environmental_cues = ""
    personality_analysis = ""
    emotional_state_str = ""
    relevant_memories = ""
    world_knowledge = ""

    for line in raw.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue
        upper = line_stripped.upper()

        if upper.startswith("INTENÇÃO:"):
            intent = line_stripped.split(":", 1)[1].strip()
        elif upper.startswith("NEEDS_WORLD:"):
            val = line_stripped.split(":", 1)[1].strip().lower()
            needs_world = val in ("yes", "sim", "true")
        elif upper.startswith("WORLD_QUERY:"):
            world_query = line_stripped.split(":", 1)[1].strip()
        elif upper.startswith("PLAN:"):
            plan = line_stripped.split(":", 1)[1].strip()
        elif upper.startswith("CURRENT_GOAL:"):
            current_goal = line_stripped.split(":", 1)[1].strip()
        elif upper.startswith("PERCEIVED_CONTEXT:"):
            perceived_context = line_stripped.split(":", 1)[1].strip()
        elif upper.startswith("ENVIRONMENTAL_CUES:"):
            environmental_cues = line_stripped.split(":", 1)[1].strip()
        elif upper.startswith("PERSONALITY_ANALYSIS:"):
            personality_analysis = line_stripped.split(":", 1)[1].strip()
        elif upper.startswith("EMOTIONAL_STATE:"):
            emotional_state_str = line_stripped.split(":", 1)[1].strip()
        elif upper.startswith("RELEVANT_MEMORIES:"):
            relevant_memories = line_stripped.split(":", 1)[1].strip()
        elif upper.startswith("WORLD_KNOWLEDGE:"):
            world_knowledge = line_stripped.split(":", 1)[1].strip()

    if not intent:
        intent = raw

    if needs_world and not world_query:
        world_query = event_summary or ""

    # Campos antigos (mantidos para compatibilidade)
    state["intent"] = intent
    state["scratch"]["needs_world"] = needs_world
    if needs_world and world_query:
        state["scratch"]["world_query"] = world_query

    # Novos campos de estado planejado
    state["plan"] = plan or intent or ""
    state["current_goal"] = current_goal or ""
    state["perceived_context"] = perceived_context or event_summary or ""
    state["environmental_cues"] = environmental_cues or ""
    state["personality_analysis"] = personality_analysis or ""
    state["emotional_state"] = emotional_state_str or emotions or ""
    state["relevant_memories"] = relevant_memories or ""
    # world_knowledge: o que o NPC já sabe, antes de qualquer nova consulta
    state["world_knowledge"] = world_knowledge or lore or ""

    _logger.info(
        "planner.out: intent=%s needs_world=%s has_query=%s world_query=%s plan=%s current_goal=%s\n",
        intent,
        needs_world,
        bool(world_query),
        world_query or "",
        state["plan"],
        state["current_goal"],
    )

    return state


# from langchain_core.messages import SystemMessage, HumanMessage
# import logging
# from core.llm import LLMHarness
# from core.state import NPCState
# from graph.prompts import sys_persona

# _llm = LLMHarness()
# _logger = logging.getLogger("npc.agents.planner")

# async def planner(state: NPCState) -> NPCState:
#     persona = state["persona"]
#     lore = state["scratch"].get("lore_hits", "")
#     emotions = ", ".join(f"{k}:{v:.2f}" for k, v in state.get("emotions", {}).items()) or "neutro"
#     prompt = [
#         sys_persona(persona),
#         SystemMessage(content=(
#             "Você é o Planejador Interno do NPC. Proponha uma intenção de alto nível "
#             "com base nos eventos, emoções e fatos. Seja curto e objetivo.\n"
#             "Formato de saída (linhas separadas, sem comentários):\n"
#             "INTENÇÃO: <texto curto>\n"
#             "NEEDS_WORLD: <yes|no>\n"
#             "WORLD_QUERY: <se NEEDS_WORLD=yes, uma consulta objetiva ao mundo; caso contrário, deixe vazio>"
#         )),
#         HumanMessage(content=f"EVENTOS: {state['scratch'].get('event_summary','(n/a)')}"),
#         HumanMessage(content=f"EMOÇÕES: {emotions}"),
#         HumanMessage(content=f"LORE:\n{lore}"),
#     ]
#     _logger.info("planner.in: emotions=%s has_lore=%s", emotions, bool(lore))
#     text = await _llm.run(prompt)
#     raw = text.strip()
#     intent = None
#     needs_world = False
#     world_query = ""
#     for line in raw.splitlines():
#         l = line.strip()
#         if l.upper().startswith("INTENÇÃO:"):
#             intent = l.split(":", 1)[1].strip()
#         elif l.upper().startswith("NEEDS_WORLD:"):
#             val = l.split(":", 1)[1].strip().lower()
#             needs_world = val in ("yes", "sim", "true")
#         elif l.upper().startswith("WORLD_QUERY:"):
#             world_query = l.split(":", 1)[1].strip()
#     if not intent:
#         intent = raw
#     if needs_world and not world_query:
#         world_query = state["scratch"].get("event_summary") or ""
#     state["intent"] = intent
#     state["scratch"]["needs_world"] = needs_world
#     if needs_world and world_query:
#         state["scratch"]["world_query"] = world_query
#     _logger.info("planner.out: intent=%s needs_world=%s has_query=%s", intent, needs_world, bool(world_query))
#     return state
