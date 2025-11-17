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
    - `perception` → `personality` → `world_model` → `planner` → `dialogue` → `critic` → END.
- **graph/runtime.py**
  - Classe `NPCGraph` inicializa o grafo (com checkpoint via `MemorySaver`).
  - Método `respond_once(user_text, thread_id, events)` prepara o estado, invoca o grafo e retorna `{thread_id, action, reply_text}`.
  - Se a ação final for do tipo `tool`, resolve via `TOOLS_REGISTRY` e inclui `fallback_say` como resposta.
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
4. Lê `action` final:
   - `type: "say"` → `reply_text = action.content`.
   - `type: "tool"` → resolve via `TOOLS_REGISTRY`, registra mensagens e usa `fallback_say` como `reply_text`.
5. Reduz as mensagens com `EpisodicMemory` e salva no checkpoint do `thread_id` (namespaced como `<npc_id>:<base_tid>`).
6. Persiste um registro mínimo da interação no `JSONMemoryStore`.

## LLM e configuração (core/llm.py)
- `LLMHarness` faz chamadas ao endpoint de Chat Completions da OpenAI.
- Variáveis:
  - `OPENAI_API_KEY`: chave para autenticar.
  - Modelos/temperatura e `timeout` configuráveis no construtor.
- Observação: se quiser trocar de provedor/modelo, adapte `LLMHarness.run` mantendo a interface de mensagens.

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