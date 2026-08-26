---
phase: 05-llm
plan: 03
subsystem: tests
tags: [pytest, monkeypatch, fastapi-testclient, escolher_extrator, fallback]

# Dependency graph
requires:
  - "app/main.py::_extrair_com_fallback(url, titulo, texto) -> tuple[Briefing, str] — do plano 05-01"
provides:
  - "test_smoke.py::test_escolher_extrator_sem_chave_devolve_heuristico — trava L-05"
  - "test_smoke.py::test_escolher_extrator_com_chave_devolve_llm — trava a escolha automatica de extrator"
  - "test_smoke.py::test_extrator_que_falha_nao_derruba_a_requisicao — teste de regressao do defeito critico da fase"
affects: [05-04-config, 05-05-llm-extractor, 05-06-visibilidade-degradacao, 05-07-cache-upgrade]

actuals:
  tokens: 545
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "monkeypatch de variavel de ambiente (setenv/delenv), nao de atributo de modulo — exige leitura de LLM_API_KEY em tempo de chamada"
    - "TestClient(app) sem context manager para nao disparar o lifespan/on_event('startup') e nao criar briefings.db"
    - "4 monkeypatches com assinatura tolerante (*args, **kwargs) em db.salvar/db.buscar para sobreviver a mudancas futuras de assinatura (plano 07)"

key-files:
  created: []
  modified:
    - "test_smoke.py"

key-decisions:
  - "Teste 3 nao assevera nada sobre o campo degradado (D-05), que so existe a partir do plano 06 — conforme planner_notes do plano"
  - "Teste 4 de D-12 (LLMExtractor.extrair() sem chave levanta erro claro) fica fora deste plano, conforme execution_order travado; entra no plano 05 junto da reescrita do LLMExtractor"

requirements-completed: [D-12, L-02, L-05, L-01]

coverage:
  - id: D1
    description: "sem LLM_API_KEY no ambiente, escolher_extrator() devolve HeuristicExtractor (trava L-05)"
    requirement: "L-05"
    verification:
      - kind: unit
        ref: "pytest -q test_smoke.py::test_escolher_extrator_sem_chave_devolve_heuristico"
        status: pass
    human_judgment: false
  - id: D2
    description: "com LLM_API_KEY no ambiente, escolher_extrator() devolve LLMExtractor"
    requirement: "L-01"
    verification:
      - kind: unit
        ref: "pytest -q test_smoke.py::test_escolher_extrator_com_chave_devolve_llm"
        status: pass
    human_judgment: false
  - id: D3
    description: "um extrator que levanta excecao produz HTTP 200 e o item volta com extrator igual a heuristico, em vez de derrubar o lote"
    requirement: "L-02"
    verification:
      - kind: unit
        ref: "pytest -q test_smoke.py::test_extrator_que_falha_nao_derruba_a_requisicao"
        status: pass
    human_judgment: false
  - id: D4
    description: "os tres testes novos rodam sem internet, sem chave de API e sem escrever em briefings.db (SPEC 14)"
    verification:
      - kind: unit
        ref: "pytest -q (6 testes, 0.42s, sem rede) + confirmacao manual de que briefings.db preexistia e nao foi tocado pelo teste 3"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-08-26
status: complete
---

# Phase 5 Plan 3: Testes do fallback (escolher_extrator + extrator quebrado) Summary

**Tres testes novos travam o caminho que segura toda a fase: sem chave o sistema roda no heuristico, com chave roda no LLM, e um extrator que levanta excecao qualquer nunca mais vira HTTP 500 — o defeito critico que motivou a fase 05.**

## Performance

- **Duration:** 15 min
- **Tasks:** 2
- **Files modified:** 1 (`test_smoke.py`)

## Accomplishments
- `test_escolher_extrator_sem_chave_devolve_heuristico` e `test_escolher_extrator_com_chave_devolve_llm` travam a escolha automatica de extrator via `monkeypatch.delenv`/`monkeypatch.setenv` de `LLM_API_KEY`, sem tocar `unittest.mock`.
- `test_extrator_que_falha_nao_derruba_a_requisicao` e o teste de regressao do defeito confirmado que motivou a fase: antes do plano 01, `main.py` capturava so `FetchError` e um extrator que levantasse qualquer outra excecao produzia HTTP 500, derrubando tambem as URLs do lote que ja tinham dado certo. O teste instancia um extrator local que sempre falha, monkeypatcha `main.escolher_extrator`, `main.buscar_html`, `db.salvar` e `db.buscar`, sobe `TestClient(main.app)` sem context manager (para nao disparar o lifespan e nao criar `briefings.db`) e confirma HTTP 200 com o item degradado para `extrator == "heuristico"`.
- Suite passou de 3 para 6 testes, todos offline, sem chave de API e sem escrita em disco: `pytest -q` roda em 0.42s.

## Task Commits

Each task was committed atomically:

1. **Task 1: Testes 1 e 2 — escolher_extrator() com e sem chave** - `85b32b7` (test)
2. **Task 2: Teste 3 — extrator que falha nao derruba a requisicao** - `a278e27` (test)

## Files Created/Modified
- `test_smoke.py` - imports estendidos (`LLMExtractor`, `escolher_extrator`, `datetime`/`timezone`, `fastapi.testclient.TestClient`, `app.db`, `app.main`); 3 testes novos acrescentados ao final, mantendo o estilo dos 3 ja existentes (funcao solta, sem classe, sem fixture, `assert` direto)

## Decisions Made
- Teste 3 nao assevera nada sobre um campo `degradado`: esse campo (D-05) so nasce no plano 06, que estende esta mesma funcao de teste com a assercao correspondente, em vez de criar um quarto teste — preservando os "quatro testes" de D-12 conforme os `planner_notes` do plano.
- `db.buscar`/`db.salvar` monkeypatchados com assinatura tolerante (`*args, **kwargs`) de proposito: o plano 07 acrescenta o parametro `llm_disponivel` a `db.buscar()`, e essa assinatura sobrevive aquela mudanca sem edicao.

## Deviations from Plan

None - plano executado exatamente como escrito. Todos os criterios de aceite de ambas as tasks (contagens de `grep`, execucao com `LLM_API_KEY` presente e ausente, ausencia de `unittest.mock`/`import pytest`/`with TestClient`, 6 testes verdes) foram verificados e batem com o estado real do disco apos o plano 01.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- O caminho de fallback (o que segura tudo o mais na fase) esta coberto por teste automatizado e nao pode regredir silenciosamente.
- Plano 04 (`config.py`) pode prosseguir: os testes 1 e 2 monkeypatcham a variavel de ambiente diretamente, entao continuam validos quando `LLM_API_KEY` passar a ser lida via `config.llm_api_key()`.
- Plano 05 (`LLMExtractor` real) e o plano 06 (campo `degradado`) tem o teste 3 pronto para ser estendido, conforme os `planner_notes` deste plano.

---
*Phase: 05-llm*
*Completed: 2026-08-26*

## Self-Check: PASSED

- FOUND: `test_smoke.py`
- FOUND: `.planning/phases/05-llm/05-03-SUMMARY.md`
- FOUND: commit `85b32b7`
- FOUND: commit `a278e27`
