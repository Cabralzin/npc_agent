import asyncio
import json
from pathlib import Path
from typing import List, Dict

import streamlit as st

from core.persona import Persona, DEFAULT_PERSONA
from core.personas import PERSONAS
from core.json_memory import JSONMemoryStore
from core.npc_manager import NPCManager
from core.voice import transcribe_audio

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

# >>> modo de entrada (texto ou áudio)
if "input_mode" not in st.session_state:
    st.session_state.input_mode = "text"  # "text" ou "audio"

# >>> texto transcrito do áudio (para processar após transcrição)
if "transcribed_text" not in st.session_state:
    st.session_state.transcribed_text = None


st.set_page_config(
    page_title="NPC Agent", 
    page_icon="🧙", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos modernos e limpos
st.markdown(
    """
    <style>
    /* Reset e base */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Header moderno */
    h1 {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    /* Chat wrapper */
    .chat-wrapper {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        height: 100%;
    }
    
    /* Chat box moderno */
    .chat-box {
        height: 35vh;
        overflow-y: auto;
        padding: 1.5rem;
        border: none;
        border-radius: 16px;
        background: linear-gradient(to bottom, #f8f9fa 0%, #ffffff 100%);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05), 0 1px 3px rgba(0, 0, 0, 0.1);
        scroll-behavior: smooth;
    }
    
    .chat-box::-webkit-scrollbar {
        width: 8px;
    }
    
    .chat-box::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    .chat-box::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 10px;
    }
    
    .chat-box::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
    
    /* Mensagens modernas */
    .msg {
        margin: 0.75rem 0;
        padding: 1rem 1.25rem;
        border-radius: 18px;
        max-width: 75%;
        word-wrap: break-word;
        line-height: 1.5;
        animation: fadeIn 0.3s ease-in;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .msg.user {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: auto;
        border-bottom-right-radius: 4px;
    }
    
    .msg.assistant {
        background: white;
        color: #1f2937;
        border: 1px solid #e5e7eb;
        margin-right: auto;
        border-bottom-left-radius: 4px;
    }
    
    /* Composer moderno */
    .composer-box {
        padding: 1rem;
        border: 2px solid #e5e7eb;
        border-radius: 16px;
        background: white;
        box-shadow: 0 2px 4px rgba(0, 0,0, 0.05);
        transition: border-color 0.3s;
    }
    
    .composer-box:focus-within {
        border-color: #667eea;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
    }
    
    .composer-row {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-top: 0.5rem;
    }
    
    .composer-row .hint {
        color: #6b7280;
        font-size: 0.875rem;
        font-style: italic;
    }
    
    /* Cards modernos */
    .stExpander {
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        background: white;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    
    /* Sidebar moderno */
    .css-1d391kg {
        background: linear-gradient(to bottom, #f8f9fa 0%, #ffffff 100%);
    }
    
    /* Botões modernos */
    .stButton > button {
        border-radius: 10px;
        border: none;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 600;
        transition: all 0.3s;
        box-shadow: 0 2px 4px rgba(102, 126, 234, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(102, 126, 234, 0.4);
    }
    
    /* Inputs modernos */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        border-radius: 10px;
        border: 1px solid #e5e7eb;
        transition: all 0.3s;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* Selectbox moderno */
    .stSelectbox > div > div {
        border-radius: 10px;
    }
    
    /* Badges e labels */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        background: #e0e7ff;
        color: #4338ca;
    }
    
    /* Divider moderno */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(to right, transparent, #e5e7eb, transparent);
        margin: 1.5rem 0;
    }
    
    /* Audio player moderno */
    .stAudio {
        border-radius: 12px;
        padding: 1.5rem;
        background: #f8f9fa;
        margin: 1rem 0;
        min-height: 80px;
    }
    
    .stAudio audio {
        width: 100%;
        height: 50px;
    }
    
    .stAudio > div {
        padding: 0.5rem 0;
    }
    </style>
    <script>
    (function() {
        let handlersAttached = new WeakSet();
        
        function attachEnterHandler(textarea) {
            // Evita adicionar múltiplos handlers ao mesmo elemento
            if (handlersAttached.has(textarea)) {
                return;
            }
            
            // Verifica se é o textarea do composer (pelo placeholder ou contexto)
            const isComposer = textarea.placeholder && 
                (textarea.placeholder.includes('Digite sua mensagem') || 
                 textarea.placeholder.includes('Enter para enviar'));
            
            if (isComposer) {
                textarea.addEventListener('keydown', function(e) {
                    // Enter puro (sem Shift, sem Ctrl, sem Alt) = enviar
                    if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
                        e.preventDefault();
                        e.stopPropagation();
                        const form = e.target.closest('form');
                        if (form) {
                            const submitButton = form.querySelector('button[type="submit"]');
                            if (submitButton) {
                                submitButton.click();
                            }
                        }
                        return false;
                    }
                }, true);
                
                handlersAttached.add(textarea);
            }
        }
        
        function setupEnterToSubmit() {
            // Procura todos os textareas dentro de forms
            const forms = document.querySelectorAll('form');
            forms.forEach(form => {
                const textareas = form.querySelectorAll('textarea');
                textareas.forEach(attachEnterHandler);
            });
        }
        
        // Executa quando a página carregar
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', setupEnterToSubmit);
        } else {
            setupEnterToSubmit();
        }
        
        // Re-executa após atualizações do Streamlit
        const observer = new MutationObserver(function() {
            setTimeout(setupEnterToSubmit, 200);
        });
        observer.observe(document.body, { childList: true, subtree: true });
    })();
    </script>
    """,
    unsafe_allow_html=True,
)

# Header moderno
st.markdown(
    """
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1>🧙 NPC Agent</h1>
        <p style="color: #6b7280; font-size: 1.1rem;">Interface para conversar com seus NPCs</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Sidebar ---
with st.sidebar:
    st.markdown(
        """
        <div style="text-align: center; padding: 1rem 0;">
            <h2 style="color: #667eea; margin-bottom: 0.5rem;">⚙️ Configuração</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Persona selection
    all_personas: Dict[str, Persona] = {**PERSONAS, **st.session_state.custom_personas}
    persona_keys = list(all_personas.keys())
    persona_labels = {k: all_personas[k].name for k in persona_keys}

    st.markdown("### 👤 Selecionar NPC")
    selected_key = st.selectbox(
        "Escolha o NPC (persona)",
        options=persona_keys if persona_keys else ["default"],
        format_func=lambda k: persona_labels.get(k, k),
        index=0 if persona_keys else None,
        label_visibility="collapsed",
    )

    # Show selected persona details
    if persona_keys:
        p = all_personas[selected_key]
    else:
        p = DEFAULT_PERSONA

    with st.expander("📋 Detalhes da Persona", expanded=False):
        st.markdown(f"**Nome:** {p.name}")
        st.markdown(f"**Estilo de fala:** {p.speech_style}")
        if p.traits:
            st.markdown(f"**Traços:** {', '.join(p.traits)}")
        if p.goals:
            st.markdown(f"**Objetivos:** {', '.join(p.goals)}")
        if p.bonds:
            st.markdown(f"**Vínculos:** {', '.join(p.bonds)}")
        if p.ideals:
            st.markdown(f"**Ideais:** {', '.join(p.ideals)}")
        if p.flaws:
            st.markdown(f"**Falhas:** {', '.join(p.flaws)}")
        if p.backstory:
            st.markdown(f"**História:** {p.backstory}")

    st.divider()

    st.markdown("### ✨ Criar Persona Personalizada")
    with st.expander("➕ Nova Persona", expanded=False):
        with st.form("create_persona_form", clear_on_submit=False):
            name = st.text_input("Nome", value="", placeholder="Ex: Lyra")
            key_id = st.text_input("ID curto", value="", placeholder="Ex: lyra2")
            backstory = st.text_area("História", placeholder="História do personagem...")
            traits = st.text_input("Traços", placeholder="Separados por vírgula")
            ideals = st.text_input("Ideais", placeholder="Separados por vírgula")
            bonds = st.text_input("Vínculos", placeholder="Separados por vírgula")
            flaws = st.text_input("Falhas", placeholder="Separados por vírgula")
            speech_style = st.text_input("Estilo de fala", value="Direta, mordaz; frases curtas", placeholder="Como o personagem fala")
            goals = st.text_input("Objetivos", placeholder="Separados por vírgula")
            submitted = st.form_submit_button("💾 Salvar Persona", use_container_width=True)
            if submitted:
                if not name or not key_id:
                    st.warning("⚠️ Preencha ao menos Nome e ID curto.")
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
                    st.success(f"✅ Persona '{name}' salva como '{key_id}'.")

    st.divider()

    st.markdown("### 🧠 Memórias do NPC")
    npc_id = selected_key
    # Ensure NPC registered
    st.session_state.manager.register(npc_id, persona=all_personas.get(selected_key, DEFAULT_PERSONA))
    store: JSONMemoryStore = st.session_state.manager.get(npc_id).store

    # Seed memory
    seed_text = st.text_input("Adicionar nota de memória", placeholder="Digite uma memória para o NPC...", label_visibility="visible")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("➕ Adicionar", use_container_width=True, key="btn_add_memory"):
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
                st.success("✅ Memória adicionada.")
            else:
                st.info("💡 Digite um texto para adicionar.")
    with col_b:
        if st.button("🔄 Recarregar", use_container_width=True, key="btn_reload_memories"):
            st.rerun()

    mem_items = store._read()
    if mem_items:
        with st.expander(f"📚 Ver últimas memórias ({len(mem_items)} total)", expanded=False):
            for i, item in enumerate(mem_items[-10:], start=1):
                with st.container():
                    st.markdown(f"**Memória #{len(mem_items) - 10 + i}**")
                    st.json(item)
                    st.markdown("---")
    else:
        st.info("💭 Sem memórias ainda. Adicione uma memória acima.")

    st.divider()

    st.markdown("### 🌍 Lore do Mundo")
    with st.expander("📝 Editar Lore", expanded=False):
        lore_text = st.text_area(
            "Itens de lore (um por linha)",
            value="\n".join(st.session_state.world_lore) if st.session_state.world_lore else "",
            height=200,
            placeholder="Digite os itens de lore do mundo, um por linha...",
            help="Cada linha será tratada como um item de conhecimento do mundo"
        )
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("💾 Salvar", use_container_width=True, key="btn_save_lore"):
                lore = [ln.strip() for ln in lore_text.splitlines() if ln.strip()]
                st.session_state.world_lore = lore
                save_world_lore(lore)
                st.success("✅ Lore salvo e aplicado.")
        with c2:
            if st.button("🔄 Recarregar", use_container_width=True, key="btn_reload_lore"):
                st.session_state.world_lore = load_world_lore()
                patch_world_lore_runtime(st.session_state.world_lore)
                st.info("ℹ️ Lore recarregado.")

# --- Main Chat ---
col_left, col_right = st.columns([2.5, 1])

with col_left:
    persona_name = all_personas.get(selected_key, DEFAULT_PERSONA).name
    st.markdown(
        f"""
        <div style="margin-bottom: 1.5rem;">
            <h2 style="color: #1f2937; margin-bottom: 0.25rem;">💬 Chat com {persona_name}</h2>
            <p style="color: #6b7280; font-size: 0.9rem;">Converse naturalmente com o NPC</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Layout de duas partes
    st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)

    # Parte 1: caixa de mensagens (fixa e rolável)
    if not st.session_state.chat:
        msgs_html = [
            "<div class='chat-box'>",
            "<div style='text-align: center; padding: 3rem 1rem; color: #9ca3af;'>",
            "<p style='font-size: 1.1rem; margin-bottom: 0.5rem;'>👋 Olá!</p>",
            "<p>Inicie uma conversa enviando uma mensagem abaixo.</p>",
            "</div>",
            "</div>"
        ]
    else:
        msgs_html = ["<div class='chat-box'>"]
        for msg in st.session_state.chat:
            role = msg.get("role", "assistant")
            content = msg.get("content", "")
            role_cls = "user" if role == "user" else "assistant"
            icon = "👤" if role == "user" else "🧙"
            msgs_html.append(f"<div class='msg {role_cls}'><strong>{icon}</strong> {content}</div>")
        msgs_html.append("</div>")
    
    st.markdown("\n".join(msgs_html), unsafe_allow_html=True)

    # >>> bloco para tocar o último áudio gerado pelo NPC
    if st.session_state.last_audio:
        st.markdown(
            """
            <div style="margin: 1rem 0; padding: 1rem; background: #f0f9ff; border-radius: 12px; border-left: 4px solid #667eea;">
                <p style="margin: 0; color: #1f2937; font-weight: 600;">🎵 Última fala em áudio</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.audio(st.session_state.last_audio, format="audio/mp3", autoplay=True)
        
        # JavaScript para garantir autoplay (alguns navegadores bloqueiam autoplay sem interação)
        st.markdown(
            """
            <script>
            (function() {
                // Aguarda o áudio ser renderizado
                setTimeout(function() {
                    const audioElements = document.querySelectorAll('audio');
                    audioElements.forEach(function(audio) {
                        // Tenta reproduzir automaticamente
                        const playPromise = audio.play();
                        if (playPromise !== undefined) {
                            playPromise.catch(function(error) {
                                // Autoplay foi bloqueado, mas o usuário pode clicar para tocar
                                console.log('Autoplay bloqueado pelo navegador:', error);
                            });
                        }
                    });
                }, 500);
            })();
            </script>
            """,
            unsafe_allow_html=True,
        )

    # Parte 2: compositor (altura fixa)
    # Toggle entre modo texto e áudio
    col_mode1, col_mode2 = st.columns([1, 1])
    with col_mode1:
        if st.button("⌨️ Modo Texto", use_container_width=True, 
                     type="primary" if st.session_state.input_mode == "text" else "secondary",
                     key="btn_text_mode"):
            st.session_state.input_mode = "text"
            st.rerun()
    with col_mode2:
        if st.button("🎤 Modo Áudio", use_container_width=True,
                     type="primary" if st.session_state.input_mode == "audio" else "secondary",
                     key="btn_audio_mode"):
            st.session_state.input_mode = "audio"
            st.rerun()
    
    # Form apenas para modo texto
    if st.session_state.input_mode == "text":
        with st.form("composer_form", clear_on_submit=True):
            st.markdown('<div class="composer-box">', unsafe_allow_html=True)
            user_input = st.text_area(
                "Mensagem", 
                key="composer_text", 
                placeholder="Digite sua mensagem aqui... (Enter para enviar, Shift+Enter para quebrar linha)", 
                height=80, 
                label_visibility="collapsed"
            )
            c1, c2 = st.columns([1, 5])
            with c1:
                send = st.form_submit_button("📤 Enviar", use_container_width=True)
            with c2:
                st.markdown(
                    '<span class="hint">💡 Dica: Enter para enviar | Shift+Enter para quebrar linha</span>', 
                    unsafe_allow_html=True
                )
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        # Modo áudio - não usa form
        user_input = None
        send = False

    st.markdown('</div>', unsafe_allow_html=True)

    # Processa modo áudio fora do form
    if st.session_state.input_mode == "audio":
        audio_input = st.audio_input(
            "Grave sua mensagem",
            key="audio_input_outer"
        )
        
        if audio_input:
            st.audio(audio_input, format="audio/wav")
            
            if st.button("🎙️ Transcrever e Enviar", use_container_width=True, key="btn_transcribe_outer"):
                try:
                    st.info("🔄 Lendo áudio...")
                    # Lê os bytes do áudio
                    audio_bytes = audio_input.read()
                    
                    if not audio_bytes:
                        st.error("❌ Erro: Áudio vazio ou não pôde ser lido.")
                    else:
                        st.info(f"✅ Áudio lido: {len(audio_bytes)} bytes")
                        # Transcreve o áudio
                        with st.spinner("🔄 Enviando para API de transcrição..."):
                            transcribed = transcribe_audio(audio_bytes, language="pt")
                            if transcribed:
                                # Armazena no session_state para processar
                                st.session_state.transcribed_text = transcribed
                                st.success(f"✅ Transcrito: {transcribed}")
                                # Força rerun para processar o texto transcrito
                                st.rerun()
                            else:
                                st.warning("⚠️ Transcrição retornou texto vazio.")
                except Exception as e:
                    st.error(f"❌ Erro ao transcrever: {e}")
                    import traceback
                    st.error(f"```\n{traceback.format_exc()}\n```")

    # Processa texto transcrito do áudio se houver
    if st.session_state.transcribed_text:
        user_input = st.session_state.transcribed_text
        send = True
        # Limpa o texto transcrito para não processar novamente
        st.session_state.transcribed_text = None
    elif st.session_state.input_mode == "text" and not user_input:
        user_input = None
        send = False

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
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 16px; margin-bottom: 1.5rem;">
            <h3 style="color: white; margin: 0 0 0.5rem 0;">📊 Sessão</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.markdown("**Thread ID atual:**")
    st.code(st.session_state.thread_id or "(nova sessão)", language="text")
    
    if st.button("🗑️ Limpar Chat", use_container_width=True, key="btn_clear_chat"):
        st.session_state.chat = []
        st.session_state.thread_id = None
        st.session_state.last_audio = None
        st.success("✅ Chat limpo!")
        st.rerun()

    st.divider()
    
    st.markdown("### 🎯 Eventos para Perceber")
    st.caption("Adicione eventos que o NPC deve perceber no próximo turno")
    
    with st.form("add_event_form", clear_on_submit=True):
        ev_source = st.text_input("Fonte", value="GM", placeholder="Ex: GM, Sistema, etc.")
        ev_type = st.selectbox("Tipo", ["info", "danger", "opportunity", "social", "environmental"], index=0)
        ev_content = st.text_area("Conteúdo", height=100, placeholder="Descreva o evento...")
        # Botão de submit - deve ser a última coisa no form
        submitted = st.form_submit_button("➕ Adicionar Evento", use_container_width=True)
        
        # Processa dentro do form para ter acesso às variáveis
        if submitted:
            if ev_content.strip():
                st.session_state.pending_events.append({
                    "source": ev_source.strip() or "GM",
                    "type": ev_type.strip() or "info",
                    "content": ev_content.strip(),
                })
                st.success("✅ Evento adicionado ao próximo turno.")
            else:
                st.warning("⚠️ Preencha o conteúdo do evento.")

    if st.session_state.pending_events:
        st.markdown(f"**📋 Eventos pendentes ({len(st.session_state.pending_events)}):**")
        for i, ev in enumerate(st.session_state.pending_events, start=1):
            with st.container():
                st.markdown(
                    f"""
                    <div style="padding: 0.75rem; background: #f8f9fa; border-radius: 8px; margin: 0.5rem 0; border-left: 3px solid #667eea;">
                        <strong>#{i}</strong> [{ev.get('source', 'GM')}] {ev.get('type', 'info')}<br>
                        <small style="color: #6b7280;">{ev.get('content', '')}</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("🗑️ Limpar Todos", use_container_width=True, key="btn_clear_all_events"):
                st.session_state.pending_events = []
                st.rerun()
        with c2:
            if st.button("➖ Remover Último", use_container_width=True, key="btn_remove_last_event"):
                if st.session_state.pending_events:
                    st.session_state.pending_events.pop()
                    st.rerun()
    else:
        st.info("💡 Nenhum evento pendente. Adicione um evento acima.")

st.markdown(
    """
    <div style="text-align: center; padding: 2rem 0; color: #9ca3af; margin-top: 3rem;">
        <p>💡 <strong>Dica:</strong> Escolha uma persona, configure memórias e lore, e comece a conversar!</p>
    </div>
    """,
    unsafe_allow_html=True,
)
