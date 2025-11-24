# npc_agent

Projeto de NPC agentizado para RPGs usando LangGraph/LangChain. Ele organiza a geração de respostas de um NPC em um fluxo de nós (percepção → personalidade → modelo de mundo → planejamento → diálogo → crítica), mantendo consistência de persona, memória e uso opcional de ferramentas.

- UI opcional em Streamlit para conversar com NPCs, gerenciar memórias, editar lore e criar personas.
- Persistência leve de interações em JSON por NPC (`memory/<npc_id>.json`).
- Suporte a múltiplos NPCs via `NPCManager` e um conjunto de personas prontas.

## Visão geral
- **NPCGraph**: fachada principal para conversar com o NPC.
- **LangGraph**: define um grafo de nós que processa a entrada do jogador e gera uma ação/resposta.
- **Persona**: descreve nome, traços, ideais, defeitos e estilo de fala do NPC.
- **Memória**: mantém um histórico curto (episódica), persistência JSON leve e um stub para memória semântica.
- **Ferramentas**: ações externas opcionais (rolar dado, hora do jogo, recuperar lore) acionadas pelo nó de diálogo.
- **UI (opcional)**: app Streamlit para chat, seleção/criação de personas, edição de lore e inspeção de memórias.

## Arquitetura
- **graph/wiring.py**
  - Monta o grafo de estado (`StateGraph[NPCState]`) com nós:
    - `perception` → `personality` → `planner` → (`world_model` se `needs_world` = yes, caso contrário `dialogue`) → `dialogue` → `critic` → END.
- **graph/runtime.py**
  - Classe `NPCGraph` inicializa o grafo (com checkpoint via `MemorySaver`).
  - Método `respond_once(user_text, thread_id, events)` prepara o estado, invoca o grafo e retorna `{thread_id, action, reply_text}`.
  - Se a ação final for do tipo `tool`, resolve via `TOOLS_REGISTRY` e inclui `fallback_say` como resposta.
  - Semeia o estado com duas `SystemMessage`: uma de persona (`sys_persona`) e outra com resumo do KB categorizado do NPC.
  - Persistência de um registro mínimo de cada interação em `memory/<npc_id>.json` (ver `core/json_memory.py`).
- **graph/prompts.py**
  - `sys_persona(persona)`: mensagem de sistema com as diretrizes da persona para guiar o modelo.

- **core/json_memory.py**
  - `JSONMemoryStore`: armazenamento simples em arquivo JSON por `npc_id` (append‑only com truncamento por tamanho).
- **core/npc_manager.py**
  - `NPCManager`: registra e gerencia múltiplos `NPCGraph` por `npc_id`; helper para semear memórias.
- **core/personas.py**
  - Personas prontas (ex.: Lyra, Mira, Irmão Calem) para uso imediato na UI ou código.
- **core/world_lore.py** e `data/world_lore.json`
  - Lista base de itens de lore; a UI permite editar e salvar em `data/world_lore.json` e aplicar em runtime.
- **streamlit_app.py**
  - Interface para chat, memórias, edição de lore e criação/seleção de personas.

## Agentes (agents/)
- **perception** (`agents/perception.py`)
  - Lê `events` estruturados do estado.
  - Monta um resumo textual (`scratch["event_summary"]`) combinando fonte, tipo e conteúdo dos eventos.
  - Limpa a lista de `events` após gerar o resumo.

- **personality** (`agents/personality.py`)
  - Lê o `event_summary` e o mapa de `emotions` atual.
  - Ajusta emoções simples com base em palavras-chave (ex.: "ameaça" aumenta vigilância, "ajuda" aumenta empatia).
  - Atualiza `state["emotions"]`, preparando terreno para decisões mais coerentes com a persona.

- **world_model** (`agents/world_model.py`)
  - Lê `scratch["world_query"]` ou, na falta dela, `scratch["event_summary"]`.
  - Usa `SemanticMemory` + `WORLD_LORE` (que pode ser editado via UI) para buscar trechos de lore relevantes.
  - Escreve o resultado em `scratch["lore_hits"]`, para uso posterior pelo planner/diálogo/crítico.

- **planner** (`agents/planner.py`)
  - Recebe persona, emoções, `event_summary`, `lore_hits` e contexto extra do `scratch`.
  - Chama o LLM com um prompt focado em PLANEJAMENTO interno do NPC.
  - Extrai e preenche campos estruturados a partir do texto de saída:
    - `intent`, `scratch["needs_world"]`, `scratch["world_query"]` (se necessário).
    - Campos de estado mental planejado: `plan`, `current_goal`, `perceived_context`, `environmental_cues`,
      `personality_analysis`, `emotional_state`, `relevant_memories`, `world_knowledge`.
  - Esses campos podem ser usados por outros nós ou pela UI para debug/telemetria.

- **dialogue** (`agents/dialogue.py`)
  - Lê a última fala do jogador (`HumanMessage` mais recente), `intent`, `lore_hits` e o estado planejado no `scratch`.
  - Chama o LLM com um prompt específico de DIÁLOGO, gerando:
    - `FALA_NPC`: fala proposta.
    - `NOTA_CRITICO`: observações para o agente crítico.
  - Salva `scratch["candidate_reply"]` e `scratch["critic_feedback"]` para consumo do `critic`.

- **critic** (`agents/critic.py`)
  - Lê a fala candidata (`candidate_reply`), lore, intenção e emoções.
  - Chama o LLM com um prompt de CRÍTICA interna que revisa a fala apenas quando necessário.
  - Produz a fala final do NPC e grava em `scratch["final_reply"]`.
  - Cria a `action` final do fluxo em `state["action"] = {"type": "say", "content": final, "audio"?: bytes}`.
  - Opcionalmente gera áudio em memória (`audio`), que o motor do jogo pode reproduzir.

## Estado (core/state.py)
`NPCState` (TypedDict):
- `npc_id`: identificador do NPC atual (usado para namespacing de memória e thread).
- `messages`: lista de mensagens (System/Human/AI) processadas no fluxo.
- `events`: lista de eventos estruturados que dão contexto adicional.
- `intent`: intenção inferida do jogador (string opcional).
- `emotions`: mapa de emoções/valências.
- `scratch`: espaço de trabalho temporário entre nós.
- `action`: saída estruturada do fluxo (ex.: `{type: "say", content: "..."}` ou `{type: "tool", name, args, fallback_say}`).
- `persona`: instância de `Persona` usada para consistência do personagem.

## Persona (core/persona.py)
- Modelo Pydantic `Persona` com: `name`, `backstory`, `traits`, `ideals`, `bonds`, `flaws`, `speech_style`, `goals`, `spoken_mode_hint`.
- `DEFAULT_PERSONA`: exemplo pronto (Lyra Ironwind) com estilo de fala e objetivos.
- Personas adicionais disponíveis em `core/personas.py` (`PERSONAS`).

## Memória (core/memory.py)
- `EpisodicMemory.reduce`: mantém apenas as últimas N mensagens (padrão 50) para controlar contexto.
- `SemanticMemory` (stub): simulate uma busca simples de lore por relevância textual.

### Persistência (core/json_memory.py)
- `JSONMemoryStore`: salva interações mínimas por NPC em `memory/<npc_id>.json`.
- Campos armazenados: timestamp, `npc_id`, `user`, `reply`, `intent` (se houver), `action` (tipo/nome/conteúdo), `events` (compactados) e extras como `thread_id`.

### Knowledge base categorizada (core/json_memory.py)
- `CategorizedMemoryStore`: mantém um KB por NPC em `memory/<npc_id>.kb.json` organizado em categorias:
  - `life`, `people`, `places`, `skills`, `objects`.
- No `NPCGraph`:
  - `_kb_system_message` lê esse arquivo e injeta uma `SystemMessage` com resumo das memórias conhecidas (usada em todo turno).
  - `_auto_memorize` usa um LLM dedicado (`NPC_KB_MODEL`, padrão `gpt-3.5-turbo`) para extrair novas/atualizadas memórias do diálogo e fazer `upsert` no KB.
  - Apenas fatos explicitamente presentes no diálogo devem ser adicionados; a política é conservadora contra alucinação.

## Ferramentas (tools/)
- Registro em `tools/__init__.py` via `TOOLS_REGISTRY`.
- Exemplos:
  - `roll_dice`: rolagem simples de dados.
  - `game_clock`: hora/tempo de jogo.
  - `recall_fact`: recuperação de fatos de lore (stub).
- O nó de diálogo pode emitir `action={type: "tool", name, args, fallback_say}`. O runtime resolve e injeta a resposta.

## Fluxo de execução (alto nível)
1. `NPCGraph.respond_once` cria um estado base (`_seed`) com `sys_persona` e chaves padrão.
2. Anexa `HumanMessage(user_text)` e quaisquer `events` opcionais.
3. Invoca o grafo assíncrono (`app.ainvoke`).
4. Ao final do grafo, o agente `critic` monta `state["action"]`:
   - Normalmente `{"type": "say", "content": <fala_final>, "audio"?: <bytes>}`.
   - `reply_text` padrão vem de `action["content"]` ou, em último caso, de `scratch["final_reply"]`.
5. Se a ação final for do tipo `tool` (casos em que outro nó peça ferramenta):
   - O runtime resolve via `TOOLS_REGISTRY`, injeta mensagens auxiliares e usa `fallback_say` como `reply_text`.
6. Reduz as mensagens com `EpisodicMemory` e salva no checkpoint do `thread_id` (namespaced como `<npc_id>:<base_tid>`).
7. Persiste um registro mínimo da interação no `JSONMemoryStore`.

## LLM e configuração (core/llm.py)
- `LLMHarness` faz chamadas ao endpoint de Chat Completions da OpenAI.
- Variáveis:
  - `OPENAI_API_KEY`: chave para autenticar.
  - Modelos/temperatura e `timeout` configuráveis no construtor.
- Observação: se quiser trocar de provedor/modelo, adapte `LLMHarness.run` mantendo a interface de mensagens.

### Voz / TTS (core/voice.py)
- `synthesize_npc_voice_bytes(text, persona)`: usa a API de voz da OpenAI para gerar áudio em memória (bytes) para a fala final.
- O agente `critic` chama essa função e, se houver sucesso, inclui `audio` em `state["action"]`.
- A persona pode ter metadados de voz (`voice_id`, `voice_style`, etc.) usados para instruções de TTS.
- O motor do jogo decide como consumir esses bytes (streaming, salvar em arquivo, enviar via rede, etc.).

### Ambiente
- Crie um `.env` com `OPENAI_API_KEY=...` ou exporte no ambiente.
- Dependências principais em `setup.py` (LangChain, LangGraph, Streamlit, Pydantic, dotenv).

## Exemplo de uso mínimo (script)
```python
import asyncio
from graph.runtime import NPCGraph

async def main():
    npc = NPCGraph()  # usa DEFAULT_PERSONA
    result = await npc.respond_once(
        "Oi, ouvi boatos sobre um pedágio na ponte.",
        thread_id="sessao_demo",
        events=[{"source": "player", "type": "mention", "content": "ponte/pedágio"}]
    )
    print(result["reply_text"])  # texto a ser exibido ao jogador

if __name__ == "__main__":
    asyncio.run(main())
```

## Exemplo com múltiplos NPCs (NPCManager)
```python
from core.npc_manager import NPCManager
from core.personas import PERSONAS
import asyncio

async def run():
    mgr = NPCManager()
    mgr.register("lyra", persona=PERSONAS["lyra"])  # ou registre on‑demand
    r1 = await mgr.respond_once("lyra", "Quem controla a ponte?", thread_id="sessao1")
    print(r1["reply_text"])

asyncio.run(run())
```

## UI (Streamlit)
- Instale as dependências e execute:
  - `streamlit run streamlit_app.py`
- Recursos na UI:
  - Chat com o NPC selecionado.
  - Criar/selecionar personas (inclui presets de `core/personas.py`).
  - Adicionar/inspecionar memórias persistidas por NPC (`memory/<npc_id>.json`).
  - Editar e salvar o lore do mundo (persistido em `data/world_lore.json`).

## Estrutura de pastas (resumo)
- `agents/`: implementação dos nós (`perception`, `personality`, `world_model`, `planner`, `dialogue`, `critic`).
- `core/`: contratos e utilidades (`persona`, `personas`, `state`, `memory`, `json_memory`, `npc_manager`, `llm`, `world_lore`).
- `graph/`: construção do grafo, runtime e prompts.
- `tools/`: ferramentas registradas e disponíveis ao NPC.
- `memory/`: persistência JSON de interações por NPC.
- `data/`: arquivo opcional `world_lore.json` com itens de lore editáveis pela UI.
- `streamlit_app.py`: app de UI para explorar o agente.

## Dicas de desenvolvimento
- Use `thread_id` fixo por sessão para manter contexto entre chamadas.
- Envie `events` quando quiser dar contexto não-verbal/estruturado ao NPC.
- As respostas estruturadas vêm em `result.action` e `result.reply_text` (conveniente para UI).
- Para estender: adicione nós em `agents/` e ligue-os em `graph/wiring.py`.
- Para múltiplos NPCs, prefira `NPCManager` para registrar/obter instâncias por `npc_id`.
- O `thread_id` é namespaced por `npc_id` automaticamente em `NPCGraph` (`<npc_id>:<seu_thread_id>`).