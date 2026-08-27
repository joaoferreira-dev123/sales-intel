---
phase: 05-llm
plan: 08
subsystem: api
tags: [fastapi, pydantic, sqlite, error-handling, tdd]

# Dependency graph
requires:
  - phase: 05-llm
    provides: gerar_briefings orchestration, HeuristicExtractor/LLMExtractor fallback chain, cache read/write via app/db.py
provides:
  - "L-02 as a structural invariant: the entire per-URL body of gerar_briefings runs inside a try with except FetchError and except Exception, so no exception from one URL can abort the batch"
  - "db.salvar failures preserve the already-generated briefing and surface AVISO_CACHE_INDISPONIVEL in BriefingResponse.degradado instead of propagating"
  - "schema-incompatible cache rows (ValidationError/TypeError on Briefing(**dados)) fall through to fresh collection (origem: novo) instead of a 500 or a false extrator: falha"
  - "degrau 3 of _extrair_com_fallback uses MSG_FALHA_GENERICA instead of interpolating the heuristic extractor's raw exception text (WR-03)"
  - "3 new offline tests persisting the two 05-VERIFICATION.md reproductions plus WR-03 coverage (7 -> 10 total)"
affects: [05-09, phase-05-verification, phase-05-review]

# Actuals (#2632)
actuals:
  tokens: 3138
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "Whole per-URL try block (cache lookup + fetch + extraction + save) with a specific except before a bare except Exception catch-all — specific-before-general ordering preserved"
    - "Narrow (ValidationError, TypeError) guard around cache-row deserialization, kept distinct from the broad catch-all so 'old data, recollect' and 'unexpected error, degrade' remain separately diagnosable"
    - "Authored-literal-only interpolation rule (D-06) now applied consistently at all three points in app/main.py: cache-write guard, degrau 2 (LLMError only), degrau 3 (no interpolation at all)"

key-files:
  created: []
  modified:
    - app/main.py
    - test_smoke.py

key-decisions:
  - "Task 1's except Exception arm covers the CLASS of failures (db.salvar, db.buscar deserialization, any other unnamed exception) rather than patching only the two routes 05-VERIFICATION.md reproduced, per the plan's explicit reasoning that a fourth route must not be able to reopen L-02"
  - "Task 2's cache-row guard wraps the entire BriefingResponse construction (not just Briefing(**dados)), because the extrator field from the cache row is also validated there and 05-09 will later tighten it to a Literal — the guard placement avoids that future change opening a new 500 path"
  - "Never interpolate str() of an unauthored exception (SQLite write failure, heuristic extractor failure) into any field the seller reads — enforced identically in the cache-write guard, degrau 2, and degrau 3"

requirements-completed: [L-02, L-06, D-01, D-05, D-06, D-10, D-12]

coverage:
  - id: D1
    description: "Falha de gravacao no cache (db.salvar) degrada apenas a URL afetada; o briefing ja gerado e preservado e sinalizado em BriefingResponse.degradado com o literal autorado, sem vazar o texto da excecao"
    requirement: "L-02"
    verification:
      - kind: integration
        ref: "test_smoke.py#test_falha_ao_salvar_no_cache_nao_derruba_o_lote"
        status: pass
    human_judgment: false
  - id: D2
    description: "Linha de cache incompativel com o schema atual de Briefing (ValidationError) vira miss de cache e forca recoleta, em vez de propagar erro ou virar item de falha; cache valido continua servindo normalmente"
    requirement: "L-02"
    verification:
      - kind: integration
        ref: "test_smoke.py#test_cache_incompativel_com_o_schema_vira_miss"
        status: pass
      - kind: manual_procedural
        ref: "python -c one-off TestClient check with a valid cache row, confirming origem == cache (non-regression, not persisted as a test)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Nenhuma excecao do corpo por URL de gerar_briefings escapa para o chamador (garantia estrutural via except Exception sem nome, verificada por introspeccao AST)"
    requirement: "L-02"
    verification:
      - kind: unit
        ref: "AST check: gerar_briefings contains a bare except Exception handler (h.name is None) after except FetchError"
        status: pass
      - kind: unit
        ref: "AST check: the for-loop body contains >=2 nested try blocks (db.salvar guard + cache-row guard)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Degrau 3 de _extrair_com_fallback (falha dupla: LLM e heuristico) usa MSG_FALHA_GENERICA em vez de interpolar a excecao do heuristico (WR-03)"
    requirement: "D-06"
    verification:
      - kind: integration
        ref: "test_smoke.py#test_falha_dupla_devolve_briefing_de_falha_sem_vazar_excecao"
        status: pass
      - kind: unit
        ref: "AST check: _extrair_com_fallback's innermost except handler binds no name"
        status: pass
    human_judgment: false
  - id: D5
    description: "pytest -q roda offline, sem chave de API e sem rede, com 10 testes verdes em menos de 3s"
    verification:
      - kind: unit
        ref: "pytest -q -> 10 passed in 0.42-0.95s across multiple runs"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-08-27
status: complete
---

# Phase 5 Plan 08: L-02 Gap Closure Summary

**Per-URL failure isolation in `gerar_briefings` becomes structural (whole-body try + bare `except Exception`), closing the one blocker (`L-02`/`CR-01`) that kept Phase 5 from sealing, and adds 3 persisted offline tests (7 -> 10) that lock the two reproductions from `05-VERIFICATION.md` plus the WR-03 message-leak fix from `05-REVIEW.md`.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-08-27T00:00:00-03:00 (approx.)
- **Completed:** 2026-08-27T00:05:48-03:00
- **Tasks:** 3
- **Files modified:** 2 (`app/main.py`, `test_smoke.py`)

## Accomplishments
- `gerar_briefings`'s entire per-URL body (cache lookup, fetch, extraction, save) now lives inside one `try`, with `except FetchError` followed by a bare `except Exception` — no exception from a single URL can abort the rest of the batch (structural L-02).
- A `db.salvar` failure preserves the briefing already generated and signals the degradation via the new `AVISO_CACHE_INDISPONIVEL` literal in `BriefingResponse.degradado`, never interpolating the raw exception text.
- A cache row that fails `Briefing(**dados)` validation (schema drift) is treated as a miss and triggers fresh collection (`origem: novo`) instead of a 500 or a false `extrator: falha`; valid cache rows are unaffected.
- The double-failure step (`degrau 3` of `_extrair_com_fallback`) now returns the authored `MSG_FALHA_GENERICA` literal instead of interpolating the heuristic extractor's exception text (WR-03), and the D-06 "only authored messages" rule is now documented consistently at all three points in the file.
- 3 new tests persist the two `05-VERIFICATION.md` reproductions and the previously-uncovered `degrau 3` path; suite grows from 7 to 10, all offline, no API key, no network, under 1s.

## Task Commits

Each task followed RED -> GREEN:

1. **Task 1: Falha de gravacao degrada so a URL afetada** - `249507c` (test), `faf53f6` (feat)
2. **Task 2: Linha de cache incompativel vira miss** - `f8599a9` (test), `cf64596` (feat)
3. **Task 3: Degrau de falha dupla para de interpolar excecao (WR-03)** - `91ceecb` (test), `aa53021` (fix)

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `app/main.py` - `AVISO_CACHE_INDISPONIVEL`/`MSG_FALHA_GENERICA` module constants; `gerar_briefings` restructured so the whole per-URL body sits inside one `try` with a nested guard around `db.salvar` and a nested `(ValidationError, TypeError)` guard around cache-row assembly, plus a new bare `except Exception` catch-all; `_extrair_com_fallback` degrau 3 stops interpolating the heuristic exception
- `test_smoke.py` - 3 new tests: `test_falha_ao_salvar_no_cache_nao_derruba_o_lote`, `test_cache_incompativel_com_o_schema_vira_miss`, `test_falha_dupla_devolve_briefing_de_falha_sem_vazar_excecao`

## Decisions Made
- Followed the plan's tracer-first ordering exactly: Task 1 establishes the structural catch-all (any exception -> failure item, batch survives), Task 2 elevates the specific cache-row route from "failure item" to "cache miss with recollection" — confirmed by observing the Task 2 test fail differently (`extrator: falha`) after Task 1 and before Task 2's fix, proving the two layers are distinct, exactly as the plan predicted.
- No new dependency, no DDL, no write to `app/db.py`/`app/schemas.py`/`app/extractor.py`/`requirements.txt` — confirmed via `git diff --stat` after each task.

## Deviations from Plan

None - plan executed exactly as written. All five acceptance-criteria command checks in each task (pytest counts, AST introspection, diff emptiness, DDL absence, timing) were run verbatim from the plan and passed on the first implementation attempt in every task.

## Must-Haves Verification (honest accounting)

**Truths (all 5 verified):**
1. Cache-write failure degrades only the affected URL, batch survives with 200 — VERIFIED (`test_falha_ao_salvar_no_cache_nao_derruba_o_lote`).
2. Schema-incompatible cache row becomes a cache miss and recollects — VERIFIED (`test_cache_incompativel_com_o_schema_vira_miss`).
3. No exception from the per-URL body of `gerar_briefings` escapes to the caller — VERIFIED via AST introspection (bare `except Exception` present, ordered after `except FetchError`) plus the two behavioral tests above exercising it.
4. Degradation messages stay short, no stack trace, no unauthored exception text, truncated at 200 chars — VERIFIED: `AVISO_CACHE_INDISPONIVEL`/`MSG_FALHA_GENERICA` are both well under 200 chars; the concatenation-then-truncate path in the `db.salvar` guard was not separately exercised by a test with a pre-existing `degradado` value (only the `degradado is None` branch is covered), so the truncation *code path* is verified by inspection and consistency with the existing `_extrair_com_fallback` pattern, not by a dedicated test. Flagged honestly rather than claimed as fully proven.
5. `pytest -q` runs offline, no API key, no network, 10 tests green — VERIFIED, consistently under 1s across multiple runs.

**Artifacts (all 5 present):**
- `app/main.py::AVISO_CACHE_INDISPONIVEL` — present
- `app/main.py::MSG_FALHA_GENERICA` — present
- `test_smoke.py::test_falha_ao_salvar_no_cache_nao_derruba_o_lote` — present
- `test_smoke.py::test_cache_incompativel_com_o_schema_vira_miss` — present
- `test_smoke.py::test_falha_dupla_devolve_briefing_de_falha_sem_vazar_excecao` — present

**Key links:** all four confirmed by direct code reading of the final `app/main.py` (whole-body try; nested `db.salvar` guard preserving the briefing and annotating `degradado`; nested cache-assembly guard converting `(ValidationError, TypeError)` to a miss; degrau 3 using `MSG_FALHA_GENERICA`).

## Known Stubs

None. No hardcoded empty values, placeholder text, or unwired data sources were introduced.

## Issues Encountered

One minor gap surfaced during honest self-review: the truncation-and-concatenation branch of the `db.salvar` guard (when `degradado` already holds a value from an LLM-then-heuristic fallback, and the cache write *also* fails) is implemented per plan but has no dedicated test — none of the three new tests drives both degradations onto the same URL simultaneously. This is a narrower gap than any `must_have`, and is not claimed as covered above. Left as-is per plan scope (not requested as a 4th test); noted here for `05-09` or a future hardening pass to pick up if desired.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The Phase 5 blocker (`L-02`/`CR-01`) is closed structurally, with persisted regression coverage. `05-09` (WR-01/WR-02, the `Literal` enum tightening and remaining test gaps) can proceed independently — it was deliberately kept separable from this plan so the blocker seals on its own.
- `app/db.py`, `app/schemas.py`, `app/extractor.py`, and `requirements.txt` remain untouched, confirmed at every task boundary.

---
*Phase: 05-llm*
*Completed: 2026-08-27*
