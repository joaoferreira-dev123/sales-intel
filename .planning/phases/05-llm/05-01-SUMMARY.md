---
phase: 05-llm
plan: 01
subsystem: api
tags: [fastapi, pydantic, pathlib, extractor-pattern]

# Dependency graph
requires: []
provides:
  - "app/main.py::_extrair_com_fallback(url, titulo, texto) -> tuple[Briefing, str] — selecao de extrator por URL com degradacao em tres degraus"
  - "app/main.py::BASE_DIR, app/main.py::STATIC_DIR — caminhos absolutos para arquivos estaticos"
affects: [05-02-fetcher-static, 05-03-testes-fallback, 05-05-llm-extractor, 05-06-visibilidade-degradacao]

actuals:
  tokens: 977
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Falha vira resultado, nunca HTTP 500: extraido do bloco except FetchError ja existente e replicado para falha de extrator"
    - "Selecao de estrategia (Extractor Protocol) chamada dentro do laco de requisicao, nunca fora, para respeitar isolamento por URL"

key-files:
  created: []
  modified:
    - "app/main.py"

key-decisions:
  - "_extrair_com_fallback devolve 2-tupla (briefing, nome_extrator) nesta wave; campo de degradacao (D-05/D-06) fica para o plano 06, conforme instrucao explicita do plano"
  - "BOM pre-existente em app/main.py removido: bloqueava a checagem de aceite do proprio plano (ast.parse com encoding utf-8 explicito) e nao tinha relacao com o defeito historico de mojibake do static/index.html (esse fica para o plano 02)"

patterns-established:
  - "Degradacao em tres degraus (extrator escolhido -> heuristico -> briefing de falha) dentro de uma unica funcao auxiliar de modulo, chamada por URL"

requirements-completed: [L-01, L-02, L-05]

coverage:
  - id: D1
    description: "escolher_extrator() passa a ser chamado dentro do laco de URLs, uma vez por URL (L-02), em vez de uma unica vez antes do laco"
    requirement: "L-02"
    verification:
      - kind: unit
        ref: "grep -c 'escolher_extrator' app/main.py == 2"
        status: pass
      - kind: unit
        ref: "python -c AST check for _extrair_com_fallback in app/main.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Qualquer excecao do extrator principal degrada para HeuristicExtractor sem virar HTTP 500; se o heuristico tambem falhar, devolve briefing de confianca baixa (L-05)"
    requirement: "L-05"
    verification:
      - kind: unit
        ref: "pytest -q (test_smoke.py, 3 testes existentes)"
        status: pass
    human_judgment: true
    rationale: "O teste automatizado que trava especificamente 'com LLM_API_KEY exportada e extrator que levanta excecao, POST /api/briefings responde 200' pertence ao plano 03 (D-12 teste 3), ainda nao escrito nesta wave; a garantia foi verificada manualmente lendo o codigo e via ast/inspect, nao por um teste de comportamento fim a fim ainda existente."
  - id: D3
    description: "StaticFiles e FileResponse usam caminho absoluto (BASE_DIR/STATIC_DIR); GET / responde 200 a partir de qualquer working directory"
    verification:
      - kind: unit
        ref: "TestClient GET / a partir de cwd temporario, status 200 e corpo iniciando com <!DOCTYPE html>"
        status: pass
      - kind: unit
        ref: "pytest -q"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-08-26
status: complete
---

# Phase 5 Plan 1: Correcoes de estabilidade (seletor de extrator + caminho estatico) Summary

**Selecao de extrator movida para dentro do laco com degradacao em tres degraus (extrator escolhido -> heuristico -> falha), e StaticFiles/FileResponse passam a usar caminho absoluto derivado de `__file__`.**

## Performance

- **Duration:** 12 min
- **Tasks:** 2
- **Files modified:** 1 (`app/main.py`)

## Accomplishments
- `escolher_extrator()` roda dentro do laco `for url_obj in req.urls`, uma vez por URL (L-02) — antes rodava uma unica vez antes do laco, o que fazia `LLM_API_KEY` exportada derrubar o lote inteiro em HTTP 500 no instante em que o `LLMExtractor` (ainda nao implementado) levantasse excecao.
- Nova funcao `_extrair_com_fallback(url, titulo, texto) -> tuple[Briefing, str]` implementa degradacao em tres degraus: extrator escolhido -> `HeuristicExtractor` -> briefing de falha com `confianca="baixa"`. Nenhum caminho levanta excecao para fora da funcao.
- `BASE_DIR` e `STATIC_DIR`, derivados de `Path(__file__).resolve()`, substituem os literais relativos `"static"` e `"static/index.html"` em `StaticFiles` e `FileResponse`. `GET /` responde 200 a partir de qualquer working directory.

## Task Commits

Each task was committed atomically:

1. **Task 1: Selecao de extrator por URL com degradacao em tres degraus** - `7f92050` (fix)
2. **Task 2: Caminho absoluto para StaticFiles e FileResponse** - `ec577ae` (fix)

## Files Created/Modified
- `app/main.py` - `_extrair_com_fallback` nova; `escolher_extrator()` movido para dentro do laco; import `HeuristicExtractor` acrescentado; `BASE_DIR`/`STATIC_DIR` novos; `StaticFiles`/`FileResponse` usando caminho absoluto; BOM pre-existente removido

## Decisions Made
- Funcao auxiliar devolve 2-tupla nesta wave (nao 3-tupla) — o campo de degradacao visivel ao vendedor (D-05/D-06) e responsabilidade do plano 06, conforme os `planner_notes` do plano.
- O `except Exception` amplo em `_extrair_com_fallback` e proposital e documentado inline: o tipo de erro do `LLMExtractor` ainda nao existe nesta fase da execucao (sera criado no plano 05), entao qualquer excecao precisa degradar.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removido BOM pre-existente em `app/main.py`**
- **Found during:** Task 1, ao rodar a checagem de aceite `python -c "...ast.parse(open('app/main.py', encoding='utf-8').read())..."`
- **Issue:** `app/main.py` ja tinha um BOM UTF-8 (`\xef\xbb\xbf`) no disco antes deste plano (confirmado via `git show HEAD:app/main.py`), nao introduzido pelas edicoes desta task. `ast.parse()` sobre uma `str` com o caractere U+FEFF no inicio levanta `SyntaxError: invalid non-printable character U+FEFF` — o parser do Python so tolera BOM quando le bytes diretamente (`compile(bytes, ...)`) ou via `open(..., encoding="utf-8-sig")`, nao quando o BOM chega como caractere dentro de uma `str` decodificada com `encoding="utf-8"` explicito. `pytest` continuava passando porque o tokenizer do CPython trata BOM de forma diferente ao importar modulos.
- **Fix:** bytes do arquivo reescritos sem o prefixo `\xef\xbb\xbf`, preservando todo o conteudo restante byte a byte.
- **Files modified:** `app/main.py`
- **Verification:** `python -c "...ast.parse(...)..."` (a propria checagem de aceite do plano) passa a imprimir `ok`; `pytest -q` continua com 3 testes verdes.
- **Committed in:** `7f92050` (parte do commit da Task 1)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Correcao necessaria para que a propria checagem de aceite da Task 1 pudesse rodar; sem ela o plano nao teria como confirmar a criacao de `_extrair_com_fallback` pela via especificada. Nenhum scope creep — o BOM e o unico ponto tocado fora do escopo literal da task, e o arquivo alterado e o mesmo que a task ja modificava.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- O sistema agora fica estavel mesmo com `LLM_API_KEY` exportada (pre-condicao para o resto da fase 05-llm): qualquer excecao do extrator escolhido degrada para o heuristico ou para briefing de falha, sem HTTP 500.
- `GET /` deixou de depender do working directory, removendo o risco de UI inacessivel citado em `.planning/codebase/CONCERNS.md`.
- Pendente para os proximos planos da fase: os testes automatizados que travam este comportamento (plano 03, D-12), `config.py`/`.env.example` (plano 04), e a implementacao real do `LLMExtractor` (plano 05) — este plano nao os cobre, apenas prepara o terreno para que eles nao quebrem a demonstracao.

---
*Phase: 05-llm*
*Completed: 2026-08-26*

## Self-Check: PASSED

- FOUND: `app/main.py`
- FOUND: `.planning/phases/05-llm/05-01-SUMMARY.md`
- FOUND: commit `7f92050`
- FOUND: commit `ec577ae`
