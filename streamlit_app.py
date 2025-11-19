import asyncio
import json
import os
from pathlib import Path
from typing import List, Dict

import streamlit as st

from core.persona import Persona, DEFAULT_PERSONA
from core.personas import PERSONAS
from core.json_memory import JSONMemoryStore
from core.npc_manager import NPCManager

# Optional: allow overriding world lore used by world_model at runtime
# We will try to load from data/world_lore.json and patch both modules' variables
WORLD_LORE_PATH = Path("data/world_lore.json")

def ensure_data_dir():
    WORLD_LORE_PATH.parent.mkdir(parents=True, exist_ok=True)

def load_world_lore() -> List[str]:
    try:
        if WORLD_LORE_PATH.exists():
            with WORLD_LORE_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [str(x) for x in data]
    except Exception:
        pass
    try:
        # Fallback to code-defined lore
        from core.world_lore import WORLD_LORE as CODE_LORE
        return list(CODE_LORE)
    except Exception:
        return []


def patch_world_lore_runtime(lore: List[str]):
    try:
        import core.world_lore as core_lore
        core_lore.WORLD_LORE = list(lore)
    except Exception:
        pass
    try:
        import agents.world_model as wm
        wm.WORLD_LORE = list(lore)  # world_model imported the list by value; patch its module attr too
    except Exception:
        pass


def save_world_lore(lore: List[str]):
    ensure_data_dir()
    with WORLD_LORE_PATH.open("w", encoding="utf-8") as f:
        json.dump(lore, f, ensure_ascii=False, indent=2)
    patch_world_lore_runtime(lore)


# Streamlit-safe async runner to avoid 'Event loop is closed'
def run_async(coro):
    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    except Exception:
        # Fallback
        return asyncio.run(coro)


# --- Session bootstrap ---
if "manager" not in st.session_state:
    st.session_state.manager = NPCManager()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

if "chat" not in st.session_state:
    st.session_state.chat = []  # list[dict]: {role: "user"|"assistant", content: str}

if "custom_personas" not in st.session_state:
    st.session_state.custom_personas: Dict[str, Persona] = {}

if "world_lore" not in st.session_state:
    st.session_state.world_lore = load_world_lore()
    patch_world_lore_runtime(st.session_state.world_lore)

if "pending_events" not in st.session_state:
    # Buffer de eventos a serem percebidos pelo NPC no próximo turno
    st.session_state.pending_events: List[Dict[str, str]] = []

# >>> novo: guardar o último áudio gerado pelo NPC para tocar na UI
if "last_audio" not in st.session_state:
    st.session_state.last_audio = None


st.set_page_config(page_title="NPC Agent", page_icon="🧙", layout="wide")
st.title("NPC Agent UI")

# Estilos do chat: painel de mensagens fixo e rolável + compositor fixo abaixo
st.markdown(
    """
    <style>
      .chat-wrapper{ display: flex; flex-direction: column; gap: 0.5rem; }
      .chat-box{ height: 60vh; overflow: auto; padding: 0.5rem 0.75rem; border: 1px solid rgba(0,0,0,0.08); border-radius: 8px; background: rgba(0,0,0,0.02); }
      .msg{ margin: 0.25rem 0; padding: 0.4rem 0.6rem; border-radius: 8px; }
      .msg.user{ background: #e8f0fe; color: #111; }
      .msg.assistant{ background: #f5f5f5; color: #111; }
      .composer-box{ height: 120px; padding: 0.5rem 0.75rem; border: 1px solid rgba(0,0,0,0.08); border-radius: 8px; background: #fff; display: flex; flex-direction: column; justify-content: space-between; }
      .composer-row{ display: flex; align-items: center; gap: 0.5rem; }
      .composer-row .hint{ color: #666; font-size: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Sidebar ---
with st.sidebar:
    st.header("Configuração")

    # Persona selection
    all_personas: Dict[str, Persona] = {**PERSONAS, **st.session_state.custom_personas}
    persona_keys = list(all_personas.keys())
    persona_labels = {k: all_personas[k].name for k in persona_keys}

    selected_key = st.selectbox(
        "Escolha o NPC (persona)",
        options=persona_keys if persona_keys else ["default"],
        format_func=lambda k: persona_labels.get(k, k),
        index=0 if persona_keys else None,
    )

    # Show selected persona details
    if persona_keys:
        p = all_personas[selected_key]
    else:
        p = DEFAULT_PERSONA

    with st.expander("Ver persona", expanded=False):
        st.write(f"Nome: {p.name}")
        st.write(f"Estilo de fala: {p.speech_style}")
        st.write("Traços:")
        st.write(", ".join(p.traits))
        st.write("Objetivos:")
        st.write(", ".join(p.goals))
        st.write("Vínculos:")
        st.write(", ".join(p.bonds))
        st.write("Ideais:")
        st.write(", ".join(p.ideals))
        st.write("Falhas:")
        st.write(", ".join(p.flaws))
        st.write("História:")
        st.write(p.backstory)

    st.divider()

    st.subheader("Criar persona personalizada")
    with st.form("create_persona_form", clear_on_submit=False):
        name = st.text_input("Nome", value="")
        backstory = st.text_area("História")
        traits = st.text_input("Traços (separe por vírgula)")
        ideals = st.text_input("Ideais (vírgulas)")
        bonds = st.text_input("Vínculos (vírgulas)")
        flaws = st.text_input("Falhas (vírgulas)")
        speech_style = st.text_input("Estilo de fala", value="Direta, mordaz; frases curtas (voz)")
        goals = st.text_input("Objetivos (vírgulas)")
        key_id = st.text_input("ID curto (ex: lyra2)")
        submitted = st.form_submit_button("Salvar persona")
        if submitted:
            if not name or not key_id:
                st.warning("Preencha ao menos Nome e ID curto.")
            else:
                persona = Persona(
                    name=name,
                    backstory=backstory or "",
                    traits=[s.strip() for s in traits.split(",") if s.strip()],
                    ideals=[s.strip() for s in ideals.split(",") if s.strip()],
                    bonds=[s.strip() for s in bonds.split(",") if s.strip()],
                    flaws=[s.strip() for s in flaws.split(",") if s.strip()],
                    speech_style=speech_style or DEFAULT_PERSONA.speech_style,
                    goals=[s.strip() for s in goals.split(",") if s.strip()],
                )
                st.session_state.custom_personas[key_id] = persona
                st.success(f"Persona '{name}' salva como '{key_id}'.")

    st.divider()

    st.subheader("Memórias do NPC")
    npc_id = selected_key
    # Ensure NPC registered
    st.session_state.manager.register(npc_id, persona=all_personas.get(selected_key, DEFAULT_PERSONA))
    store: JSONMemoryStore = st.session_state.manager.get(npc_id).store

    # Seed memory
    seed_text = st.text_input("Adicionar nota de memória")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Adicionar"):
            if seed_text.strip():
                rec = store.minimal_record(
                    user_text="[seed]",
                    reply_text=None,
                    intent=None,
                    action={"type": "seed"},
                    events=None,
                    extras={"note": seed_text.strip()},
                )
                store.append(rec)
                st.success("Memória adicionada.")
            else:
                st.info("Digite um texto para adicionar.")
    with col_b:
        if st.button("Recarregar memórias"):
            pass

    mem_items = store._read()
    if mem_items:
        with st.expander("Ver últimas memórias", expanded=False):
            for item in mem_items[-20:]:
                st.json(item)
    else:
        st.caption("Sem memórias ainda.")

    st.divider()

    st.subheader("Lore do Mundo")
    with st.expander("Editar lore (um item por linha)", expanded=False):
        lore_text = st.text_area(
            "Itens de lore",
            value="\n".join(st.session_state.world_lore) if st.session_state.world_lore else "",
            height=180,
        )
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Salvar lore"):
                lore = [ln.strip() for ln in lore_text.splitlines() if ln.strip()]
                st.session_state.world_lore = lore
                save_world_lore(lore)
                st.success("Lore salvo e aplicado em runtime.")
        with c2:
            if st.button("Recarregar do disco"):
                st.session_state.world_lore = load_world_lore()
                patch_world_lore_runtime(st.session_state.world_lore)
                st.info("Lore recarregado.")

# --- Main Chat ---
col_left, col_right = st.columns([2, 1])
with col_left:
    st.subheader(f"Chat com: {all_personas.get(selected_key, DEFAULT_PERSONA).name}")

    # Layout de duas partes
    st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)

    # Parte 1: caixa de mensagens (fixa e rolável)
    msgs_html = ["<div class='chat-box'>"]
    for msg in st.session_state.chat:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        role_cls = "user" if role == "user" else "assistant"
        msgs_html.append(f"<div class='msg {role_cls}'>{content}</div>")
    msgs_html.append("</div>")
    st.markdown("\n".join(msgs_html), unsafe_allow_html=True)

    # >>> bloco para tocar o último áudio gerado pelo NPC
    if st.session_state.last_audio:
        st.markdown("**Última fala em áudio:**")
        st.audio(st.session_state.last_audio, format="audio/mp3")

    # Parte 2: compositor (altura fixa)
    with st.form("composer_form", clear_on_submit=True):
        st.markdown('<div class="composer-box">', unsafe_allow_html=True)
        user_input = st.text_area("Mensagem", key="composer_text", placeholder="Digite sua mensagem", height=70, label_visibility="collapsed")
        c1, c2 = st.columns([1,5])
        with c1:
            send = st.form_submit_button("Enviar")
        with c2:
            st.markdown('<span class="hint">Shift+Enter para quebrar linha</span>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    if user_input and send:
        # Append user message
        st.session_state.chat.append({"role": "user", "content": user_input})

        # Ensure the selected persona is registered on the manager
        npc_id = selected_key
        persona = all_personas.get(selected_key, DEFAULT_PERSONA)
        st.session_state.manager.register(npc_id, persona=persona)

        # Respond using the graph
        async def get_reply():
            return await st.session_state.manager.respond_once(
                npc_id=npc_id,
                user_text=user_input,
                thread_id=st.session_state.thread_id,
                events=st.session_state.pending_events if st.session_state.pending_events else None,
            )

        try:
            result = run_async(get_reply())
            st.session_state.thread_id = result.get("thread_id", st.session_state.thread_id)
            reply_text = result.get("reply_text") or (result.get("action") or {}).get("content") or "(sem resposta)"

            # >>> captura o áudio vindo do NPCGraph/NPCManager
            audio_bytes = result.get("audio") or (result.get("action") or {}).get("audio")
            st.session_state.last_audio = audio_bytes

        except Exception as e:
            reply_text = f"Erro ao obter resposta: {e}"

        st.session_state.chat.append({"role": "assistant", "content": reply_text})

        # Após enviar, limpamos os eventos pendentes para não reenviá-los no próximo turno
        st.session_state.pending_events = []

        # Força atualização visual
        st.rerun()

with col_right:
    st.subheader("Sessão")
    st.caption("Thread ID atual")
    st.code(st.session_state.thread_id or "(novo)" , language="text")
    if st.button("Limpar chat e thread"):
        st.session_state.chat = []
        st.session_state.thread_id = None
        st.session_state.last_audio = None  # >>> limpar áudio também
        st.rerun()

    st.divider()
    st.subheader("Eventos para perceber")
    with st.form("add_event_form", clear_on_submit=True):
        ev_source = st.text_input("Fonte", value="GM")
        ev_type = st.text_input("Tipo", value="info")
        ev_content = st.text_area("Conteúdo", height=80)
        add_ev = st.form_submit_button("Adicionar evento")
        if add_ev:
            if ev_content.strip():
                st.session_state.pending_events.append({
                    "source": ev_source.strip() or "GM",
                    "type": ev_type.strip() or "info",
                    "content": ev_content.strip(),
                })
                st.success("Evento adicionado ao próximo turno.")
            else:
                st.info("Preencha o conteúdo do evento.")

    if st.session_state.pending_events:
        st.caption("Eventos pendentes (enviados no próximo turno):")
        for i, ev in enumerate(st.session_state.pending_events, start=1):
            st.json({"#": i, **ev})
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Limpar eventos"):
                st.session_state.pending_events = []
                st.experimental_rerun()
        with c2:
            if st.button("Remover último"):
                if st.session_state.pending_events:
                    st.session_state.pending_events.pop()
                    st.experimental_rerun()

st.caption("Para iniciar: escolha uma persona, opcionalmente edite o lore do mundo e memórias, e envie uma mensagem.")
