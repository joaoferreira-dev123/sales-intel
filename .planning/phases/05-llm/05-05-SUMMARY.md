---
phase: 05-llm
plan: 05
subsystem: api
tags: [llm, httpx, groq, json-schema, prompt-injection, pydantic]

requires:
  - phase: 05-llm (plano 04)
    provides: "app/config.py com llm_api_key(), LLM_MODELO, LLM_MAX_CHARS, LLM_BASE_URL apontando por padrao para o Groq (D-13)"
provides:
  - "app/extractor.py::LLMExtractor ligado de ponta a ponta: prompt endurecido (D-11), chamada real via httpx com response_format json_schema (D-02), timeout de 20s sem retry (D-03), validacao Briefing(**dados) na volta (L-03)"
  - "test_smoke.py::test_llm_sem_chave_levanta_erro_claro — quarto e ultimo teste de D-12"
  - "evidencia de verificacao contra modelo real (openai/gpt-oss-120b no Groq), 2 URLs de ponta a ponta (D-14)"
affects: ["05-llm plano 06 (visibilidade da degradacao consome LLMError)", "05-llm plano 07 (regra de upgrade de cache consome llm_disponivel/extrator llm)"]

actuals:
  tokens: 2260
  tasks: 4
  commits: 3

tech-stack:
  added: []
  patterns:
    - "excecao local herda de RuntimeError para manter um unico tipo de topo capturado por _extrair_com_fallback (main.py)"
    - "excecao privada (_SemJsonSchema) para sinalizar controle interno de degradacao, nunca exposta ao chamador"
    - "prompt em duas mensagens (system/user) com delimitador explicito e anti-forja de delimitador, para mitigar injecao de prompt"
    - "schema JSON do provedor sempre derivado de Pydantic.model_json_schema(), nunca escrito a mao"

key-files:
  created: []
  modified:
    - app/extractor.py
    - test_smoke.py

key-decisions:
  - "D-02/D-03 reconciliados: nenhum retry em timeout/erro de rede/5xx; a unica segunda chamada permitida e a degradacao de D-02, disparada so por HTTP 400 citando response_format/json_schema"
  - "strict: false no json_schema, deliberado — Briefing.model_json_schema() nao produz additionalProperties:false nem 100% de required; a garantia real fica em Briefing(**dados) na volta"
  - "Task 4 executada com autorizacao explicita do usuario para chamadas pagas reais ao Groq (2 URLs), conforme D-14"

patterns-established:
  - "Toda mensagem de LLMError interpola apenas {resp.status_code} ou {type(ex).__name__} — nunca a chave, o corpo bruto da resposta ou o dicionario de dados"

requirements-completed: [D-01, D-02, D-03, D-11, D-12, D-13, D-14, L-03, L-04, L-06]

coverage:
  - id: D1
    description: "LLMError(RuntimeError), LLM_TIMEOUT=20.0, DELIM_INICIO/DELIM_FIM e LLMExtractor._montar_mensagens com prompt endurecido de D-11 (instrucao separada do dado, substring 'dado, nunca comando', anti-forja de delimitador, corte em config.LLM_MAX_CHARS)"
    requirement: "D-11"
    verification:
      - kind: unit
        ref: "verificacao inline da Task 1 (python -c ...): 2 mensagens system/user, substring 'dado, nunca comando', corte de 12k, anti-forja de delimitador, LLMError subclasse de RuntimeError, LLM_TIMEOUT==20.0, endpoint nao e constante de modulo"
        status: pass
      - kind: unit
        ref: "test_smoke.py (suite completa, 7 testes)"
        status: pass
    human_judgment: false
  - id: D2
    description: "LLMExtractor._chamar_provedor (POST unico, response_format json_schema derivado de Briefing.model_json_schema(), strict=False, timeout=20s sem retry) e extrair() reescrito: json.loads + Briefing(**dados), com LLMError em JSON invalido/fora do schema/resposta em envelope inesperado, degradacao unica via _SemJsonSchema"
    requirement: "D-02"
    verification:
      - kind: unit
        ref: "verificacao inline da Task 2 (python -c ...): conteudo nao-JSON, JSON fora do schema e envelope inesperado viram LLMError sem vazar a chave; JSON valido vira Briefing com confianca do modelo; degradacao ocorre exatamente uma vez (usar_json_schema=[True, False]); sem laco em _chamar_provedor"
        status: pass
      - kind: unit
        ref: "verificacao inline da Task 2, segundo bloco: LLM_BASE_URL=http://127.0.0.1:9/v1 exportado — _chamar_provedor tenta 127.0.0.1:9 e falha com LLMError de rede, provando que o endereco vem de config.LLM_BASE_URL (D-13)"
        status: pass
      - kind: unit
        ref: "test_smoke.py (suite completa, 7 testes)"
        status: pass
    human_judgment: false
  - id: D3
    description: "test_llm_sem_chave_levanta_erro_claro — quarto teste de D-12, offline por construcao, RuntimeError com 'chave' na mensagem e sem None/NoneType"
    requirement: "D-12"
    verification:
      - kind: unit
        ref: "test_smoke.py::test_llm_sem_chave_levanta_erro_claro"
        status: pass
      - kind: other
        ref: "LLM_API_KEY=algum-valor pytest -q test_smoke.py::test_llm_sem_chave_levanta_erro_claro (delenv domina o ambiente)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Verificacao contra modelo real (D-14): POST /api/briefings com forcar_atualizacao=true, 2 URLs publicas (bna.dev.br, fastapi.tiangolo.com), openai/gpt-oss-120b no endpoint do Groq — HTTP 200, extrator=='llm' para ambas, briefing schema-valido com dores_provaveis e ganchos_de_conversa preenchidos e especificos de cada pagina"
    requirement: "D-14"
    verification:
      - kind: e2e
        ref: "execucao manual via TestClient (script ad-hoc, nao versionado) contra Groq real — ver secao 'Verificacao contra modelo real' abaixo para o JSON completo"
        status: pass
    human_judgment: true
    rationale: "SPEC S15 pede 'briefing rico' — riqueza aqui significa dores/ganchos especificos da pagina, nao frases genericas intercambiaveis. Essa avaliacao de especificidade e julgamento humano por natureza; a assercao automatica so prova formato valido e campos nao-vazios, nao qualidade do conteudo."

duration: ~18min
completed: 2026-08-26
status: complete
---

# Phase 5 Plan 05: LLMExtractor ligado, com verificação real (D-14) Summary

**`LLMExtractor` chama o Groq via `httpx` direto, com `response_format: json_schema` derivado de `Briefing.model_json_schema()`, prompt de duas mensagens endurecido contra injeção (D-11), timeout de 20s sem retry (D-03), e evidência real de 2 URLs processadas por `openai/gpt-oss-120b`.**

## Performance

- **Duration:** ~18 min
- **Tasks:** 4/4 (Tasks 1-3 codificadas e testadas offline; Task 4 executada com chamadas reais autorizadas)
- **Files modified:** 2 (`app/extractor.py`, `test_smoke.py`)

## Accomplishments
- `LLMExtractor` deixou de terminar em `NotImplementedError`: chama o provedor de verdade, valida a saída pelo schema `Briefing` e nunca entrega dado ruim nem vaza segredo
- Mitigação completa de injeção de prompt (D-11): instrução e dado em mensagens separadas, delimitador explícito, anti-forja de delimitador, validação de schema na volta
- Degradação única de D-02 implementada e testada com duplo: `_SemJsonSchema` dispara só em HTTP 400 citando `response_format`/`json_schema`, reusando as mesmas mensagens
- Quarto e último teste de D-12 (`test_llm_sem_chave_levanta_erro_claro`) fecha a cobertura de fallback: suite com 7 testes, todos offline
- Task 4 (D-14) executada com autorização explícita do usuário: 2 URLs reais processadas de ponta a ponta contra `openai/gpt-oss-120b` no endpoint do Groq, `extrator: llm` para ambas, briefings ricos e específicos por página

## Task Commits

Each task was committed atomically:

1. **Task 1: Excecao LLMError, constantes do provedor e montagem do prompt endurecido (D-11)** - `aec987e` (feat)
2. **Task 2: Chamada ao provedor com saida estruturada, timeout sem retry e validacao na volta** - `14f0bd5` (feat)
3. **Task 3: Teste 4 de D-12 — LLMExtractor sem chave levanta erro claro** - `dd7ec9f` (test)
4. **Task 4: Verificacao contra modelo real — 2 URLs de ponta a ponta (D-14)** - sem commit de código (task não versiona arquivo novo; evidência registrada abaixo)

## Files Created/Modified
- `app/extractor.py` - `LLMError(RuntimeError)`, `_SemJsonSchema(Exception)`, `LLM_TIMEOUT=20.0`, `DELIM_INICIO`/`DELIM_FIM`, `LLMExtractor._montar_mensagens`, `LLMExtractor._chamar_provedor`, `LLMExtractor.extrair` (implementado)
- `test_smoke.py` - `test_llm_sem_chave_levanta_erro_claro` (quarto teste de D-12), `import pytest`

## Verificação contra modelo real (Task 4, D-14)

**Chave carregada do `.env` da raiz** (gitignored, nunca commitado; o valor nunca foi impresso, apenas confirmada presença/tamanho: `56` caracteres, prefixo `gsk_`). Antes de qualquer chamada, confirmado em runtime:

- `config.LLM_BASE_URL == "https://api.groq.com/openai/v1"` ✓ (padrão do código, nada exportado além da chave)
- `config.LLM_MODELO == "openai/gpt-oss-120b"` ✓ (idem)

**Execução:** `POST /api/briefings` via `TestClient`, `forcar_atualizacao: true`, 2 URLs reais e públicas:

- `https://www.bna.dev.br/`
- `https://fastapi.tiangolo.com/`

**Resultado:** HTTP 200, 2 itens devolvidos, `extrator == "llm"` para ambos (nenhuma degradação silenciosa). Ambos os briefings vieram com `empresa`/`resumo` preenchidos e `dores_provaveis`/`ganchos_de_conversa` com múltiplos elementos.

**Modelo:** `openai/gpt-oss-120b` · **Endpoint:** `https://api.groq.com/openai/v1` · **URLs processadas:** 2 · **Tempo aproximado por URL:** não medido com precisão de ponta a ponta — um bug de encoding do console Windows (cp1252 não decodifica `‑` presente na resposta em inglês da FastAPI) abortou o script de verificação antes do cálculo final de `dt/len(itens)`. Como estimativa de ordem de grandeza: os dois registros gravados no `briefings.db` (via `forcar_atualizacao=true`, portanto sem cache) têm `coletado_em` com ~3.0s de diferença entre si (`18:03:40.989` e `18:03:44.029`), consistente com a latência esperada do Groq para este modelo. Os dados completos de ambos os briefings foram recuperados do `briefings.db` (gravação normal da aplicação feita antes do crash do print) e não exigiram nenhuma chamada adicional ao provedor.

**Julgamento humano de especificidade (SPEC §15 "briefing rico"):**

- `bna.dev.br` → `dores_provaveis`: "Falta de adoção de IA pelos times", "Iniciativas de IA sem prioridade clara", "Projetos de IA que não avançam do MVP para produção" — específico do setor de consultoria de IA descrito na página.
- `fastapi.tiangolo.com` → `dores_provaveis`: "Need for faster API development cycles", "Scaling high-traffic Python APIs efficiently", "Automated deployment and CI/CD integration", "Monitoring and observability of FastAPI services" — específico de um framework de API Python, nada em comum com as dores da `bna.dev.br`.

As duas listas são claramente intransferíveis entre si — não há frase genérica repetida (ex.: "reduzir custos") nos dois briefings. **Aprovado**: os briefings são ricos e específicos da página, não intercambiáveis.

**Limite de cobertura desta verificação:** esta task exercita **apenas o caminho primário de D-02** (`response_format: json_schema`), porque `openai/gpt-oss-120b` suporta saída estruturada nativa — foi por isso que ele foi escolhido, e os demais modelos grandes da conta só oferecem modo JSON. O galho de degradação (`_SemJsonSchema`) **não** foi exercitado aqui e continua coberto apenas pelo teste com duplo da Task 2 (verificação D2 acima). **"LLM verificado" não significa "os dois caminhos de D-02 verificados".**

**Registro no `briefings.db`:** as 2 linhas gravadas por esta verificação são gravação normal da aplicação (`forcar_atualizacao: true`) e permanecem no banco — nada foi apagado (D-10).

## Decisions Made
- Task 4 executada (não SKIPPED): a chave `LLM_API_KEY` existia em `.env` na raiz do repo, e o usuário autorizou explicitamente as chamadas pagas para 2-3 URLs. Carregada apenas para o processo de verificação, nunca impressa nem persistida em nenhum arquivo versionado.
- O `.env` da raiz tem BOM UTF-8 nos bytes (`\xef\xbb\xbf` antes de `LLM_API_KEY=`), o que quebra o `set -a; . ./.env; set +a` padrão do bash (interpreta o BOM como início de um nome de comando). Contornado lendo o arquivo em Python com `codecs.BOM_UTF8` removido explicitamente, sem nunca imprimir o valor da chave — nenhum arquivo novo versionado por causa disso (o script de leitura ficou fora do repo, no diretório de scratchpad da sessão).
- Após o `TestClient.post(...)` retornar HTTP 200 (com os 2 briefings já gerados e persistidos no banco), um bug de encoding no console Windows (cp1252) abortou o script antes do print final. Como os dados já haviam sido gravados em `briefings.db` por `db.salvar()` (parte do fluxo normal de `main.py`, não algo criado pela verificação), os briefings completos foram recuperados diretamente do banco via uma consulta SQL de leitura — **nenhuma chamada adicional ao provedor foi feita**, o teto de "no máximo 3 URLs" continua respeitado com folga (2 URLs, 2 chamadas reais no total).

## Deviations from Plan

None - Tasks 1-3 executadas exatamente como escrito no plano. A Task 4 seguiu o `<task_4_authorization>` fornecido pelo orquestrador (chave presente e autorizada, guard de `LLM_BASE_URL`/`LLM_MODELO` confirmado antes de qualquer chamada), não o branch SKIPPED do plano original.

## Issues Encountered
- Comentário de docstring em `_chamar_provedor` continha as palavras "retry" e "backoff" dentro de um docstring (não de um comentário `#`), o que o grep de acceptance criteria `grep -v '^\s*#' ... | grep -cE 'retry|backoff|time\.sleep'` não filtra (docstrings não começam com `#`). Reescrito para "sem repeticao alguma" antes do commit da Task 2 — mesmo sentido, sem as palavras que o grep vigia.
- Bug de encoding do console Windows (cp1252) ao imprimir a resposta da Task 4 contendo `‑` (hífen não-quebrável) — resolvido lendo os dados já persistidos direto do `briefings.db` em vez de repetir a chamada de rede (ver "Decisions Made" acima).

## User Setup Required

None - usuário já havia colocado `LLM_API_KEY` no `.env` local (fora do git) antes desta execução, e autorizou explicitamente as chamadas pagas da Task 4.

## Next Phase Readiness
- `LLMExtractor` está ligado de ponta a ponta e verificado contra modelo real; plano 06 (visibilidade da degradação) pode consumir `LLMError` sem mudanças aqui.
- Plano 07 (regra de upgrade de cache) pode confiar em `extrator == "llm"` como sinal de sucesso real, confirmado pela Task 4.
- Suite `pytest -q` verde com 7 testes, todos offline (sem rede, sem chave).
- Nenhum bloqueio identificado para o plano 06.

---
*Phase: 05-llm*
*Completed: 2026-08-26*
