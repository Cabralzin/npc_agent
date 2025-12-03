from langchain_core.messages import SystemMessage, HumanMessage
import logging
from core.llm import LLMHarness
from core.state import NPCState
from graph.prompts import sys_persona
from core.models_preset import PLANNER_MODEL

_llm = LLMHarness(model=PLANNER_MODEL)
_logger = logging.getLogger("npc.agents.planner")


async def planner(state: NPCState) -> NPCState:
    persona = state["persona"]
    scratch = state.get("scratch", {}) or {}

    lore = scratch.get("lore_hits", "") or ""
    event_summary = scratch.get("event_summary", "(n/a)")
    emotions_dict = state.get("emotions", {}) or {}
    emotions = ", ".join(f"{k}:{v:.2f}" for k, v in emotions_dict.items()) or "neutro"

    # Informações do agente de emoção dinâmica
    emotion_justification = scratch.get("emotion_justification", "")
    dynamic_emotion_info = ""
    if emotion_justification:
        dynamic_emotion_info = f"JUSTIFICATIVA DAS EMOÇÕES DINÂMICAS: {emotion_justification}"

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
    if dynamic_emotion_info:
        extra_ctx_lines.append(dynamic_emotion_info)

    extra_ctx = "\n".join(extra_ctx_lines) if extra_ctx_lines else "(sem contexto extra relevante)"

    # Contexto percebido e pistas ambientais do context_awareness
    perceived_context_from_awareness = state.get("perceived_context") or scratch.get("perceived_context", "")
    environmental_cues_from_awareness = state.get("environmental_cues") or scratch.get("environmental_cues", "")

    prompt = [
        sys_persona(persona),
        SystemMessage(
            content=(
                "Você é o Planejador Interno do NPC. O fluxo do sistema é:\n"
                "- Primeiro: percepção e personalidade já foram processadas.\n"
                "- Depois: o agente de emoção dinâmica ajustou as emoções baseado no histórico completo de interações.\n"
                "- Em seguida: o agente de consciência contextual analisou a situação atual e gerou perceived_context e environmental_cues.\n"
                "- Agora: você planeja a intenção e o estado mental do NPC considerando essas informações contextuais.\n"
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
                "- As EMOÇÕES fornecidas foram ajustadas dinamicamente pelo agente de emoção dinâmica baseado no histórico.\n"
                "- Se houver uma JUSTIFICATIVA DAS EMOÇÕES DINÂMICAS, use-a para entender o contexto emocional profundo do NPC.\n"
                "- Considere como as emoções evoluíram ao longo das interações passadas ao planejar a intenção.\n"
                "- Cada campo deve ter 1 ou 2 frases, no máximo; seja funcional e direto.\n"
                "- Se marcar NEEDS_WORLD = yes, a WORLD_QUERY deve ser específica e prática, algo que o agente de mundo "
                "possa realmente responder (ex.: posição de ameaças, recursos próximos, estado de um local, etc.).\n"
                "- NÃO antecipe o resultado da WORLD_QUERY: o que virá depois será colocado em world_result "
                "e usado pelo diálogo em outro momento.\n"
                "- O campo WORLD_KNOWLEDGE deve descrever apenas o que o NPC já sabe antes de qualquer nova consulta.\n"
                "- Use emoções dinâmicas e lore para deixar o planejamento coerente e contextualizado, sem exagerar.\n"
                "- O campo EMOTIONAL_STATE deve refletir não apenas as emoções atuais, mas também como elas foram ajustadas "
                "dinamicamente baseado no histórico de interações.\n"
                "- Se não tiver informação suficiente para algum campo, preencha com algo genérico mas útil.\n"
                "\n"
                "FORMATO DE SAÍDA (exatamente essas linhas, sem comentários extra):\n"
                "INTENÇÃO: <texto curto>\n"
                "NEEDS_WORLD: <yes|no>\n"
                "WORLD_QUERY: <consulta ou vazio>\n"
                "PLAN: <plano de alto nível do NPC>\n"
                "CURRENT_GOAL: <objetivo imediato na cena>\n"
                "PERCEIVED_CONTEXT: <use o valor fornecido do context_awareness, ou refine se necessário>\n"
                "ENVIRONMENTAL_CUES: <use o valor fornecido do context_awareness, ou refine se necessário>\n"
                "PERSONALITY_ANALYSIS: <como a personalidade influencia sua reação>\n"
                "EMOTIONAL_STATE: <descrição curta do estado emocional>\n"
                "RELEVANT_MEMORIES: <memórias ou experiências que afetam a decisão>\n"
                "WORLD_KNOWLEDGE: <fatos do mundo que o NPC traz para o momento>"
            )
        ),
        HumanMessage(content=f"EVENTOS: {event_summary}"),
        HumanMessage(content=f"EMOÇÕES: {emotions}"),
        HumanMessage(content=f"LORE:\n{lore}"),
        HumanMessage(content=f"CONTEXTO PERCEBIDO (do context_awareness): {perceived_context_from_awareness or '(não fornecido)'}"),
        HumanMessage(content=f"PISTAS AMBIENTAIS (do context_awareness): {environmental_cues_from_awareness or '(não fornecido)'}"),
        HumanMessage(content=f"OUTROS DADOS INTERNOS (SCRATCH):\n{extra_ctx}"),
    ]

    _logger.info(
        "planner.in: emotions=%s has_lore=%s has_emotion_justification=%s",
        emotions,
        bool(lore),
        bool(emotion_justification)
    )

    text = await _llm.run(prompt)
    raw = (text or "").strip()

    intent = None
    needs_world = False
    world_query = ""

    # Novos campos de estado mental
    plan = ""
    current_goal = ""
    # Inicializa com valores do context_awareness se disponíveis
    perceived_context = state.get("perceived_context") or scratch.get("perceived_context", "")
    environmental_cues = state.get("environmental_cues") or scratch.get("environmental_cues", "")
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
            # Se o planner gerou um novo valor, usa ele; senão mantém o do context_awareness
            planner_perceived_context = line_stripped.split(":", 1)[1].strip()
            if planner_perceived_context:
                perceived_context = planner_perceived_context
        elif upper.startswith("ENVIRONMENTAL_CUES:"):
            # Se o planner gerou um novo valor, usa ele; senão mantém o do context_awareness
            planner_environmental_cues = line_stripped.split(":", 1)[1].strip()
            if planner_environmental_cues:
                environmental_cues = planner_environmental_cues
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
    if needs_world:
        # Define para onde retornar após world_model (retorna para si mesmo)
        state["scratch"]["needs_world"] = True
        state["scratch"]["world_model_return_to"] = "planner"
        if world_query:
            state["scratch"]["world_query"] = world_query
    else:
        # Limpa os flags se não precisar mais
        state["scratch"].pop("needs_world", None)
        state["scratch"].pop("world_query", None)
        state["scratch"].pop("world_model_return_to", None)

    # Novos campos de estado planejado
    state["plan"] = plan or intent or ""
    state["current_goal"] = current_goal or ""
    # Usa os valores gerados pelo planner se houver, senão mantém os do context_awareness
    if perceived_context:
        state["perceived_context"] = perceived_context
    elif not state.get("perceived_context"):
        state["perceived_context"] = perceived_context_from_awareness or event_summary or ""
    if environmental_cues:
        state["environmental_cues"] = environmental_cues
    elif not state.get("environmental_cues"):
        state["environmental_cues"] = environmental_cues_from_awareness or ""
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
