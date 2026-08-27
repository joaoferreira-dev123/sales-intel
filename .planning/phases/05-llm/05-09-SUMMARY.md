---
phase: 05-llm
plan: 09
subsystem: api
tags: [pydantic, sqlite, prompt-injection, httpx, tdd, testing]

# Dependency graph
requires:
  - phase: 05-llm
    provides: "the 05-08 cache-row guard around BriefingResponse construction (ValidationError/TypeError -> cache miss instead of 500), which is what makes closing extrator to a Literal safe"
provides:
  - "BriefingResponse.extrator closed to Literal['llm', 'heuristico', 'falha'] (SPEC S8), enforced by Pydantic"
  - "A stale cache row with an out-of-enum extrator value becomes a cache miss (200, origem: novo) instead of a ValidationError escaping as a 500"
  - "Persisted, offline, deterministic test coverage for the three highest-leverage behaviors added in Phase 5: the D-09 cache-upgrade predicate (both directions), the D-11 delimiter anti-forgery in _montar_mensagens, and the D-02 json_schema degradation branch (including the D-03 no-loop guarantee on a second 400)"
affects: [phase-06, phase-05-verification-reread]

# Actuals (#2632)
actuals:
  tokens: 1450
  tasks: 3
  commits: 6
  raw_tokens: 8100

tech-stack:
  added: []
  patterns:
    - "Hand-written httpx.Client double (class-level corpos_recebidos/roteiro lists reset per test before monkeypatch install) instead of a new mocking dependency — keeps requirements.txt untouched per L-06/D-01"
    - "Class-level fake objects reused across tests via monkeypatch.setattr rather than nested per-test classes, matching the file's existing flat/functional test style"

key-files:
  created: []
  modified:
    - app/schemas.py
    - test_smoke.py

key-decisions:
  - "Task 1 followed strict RED-GREEN: the new test was run and confirmed failing (origem == cache) against the pre-fix str-typed field before editing schemas.py, proving the enum-closure fix is what makes the test pass, not an artifact of test construction"
  - "Tasks 2 and 3 are regression-lock tests only: the behaviors they test (D-09 upgrade rule, D-11 delimiter anti-forgery, D-02 degradation branch) were already correctly implemented, so all 5 new tests in Tasks 2-3 passed on first run with zero production-code changes — this is the expected and intended outcome per the plan (the goal is persisted coverage against future regression, not a new fix)"
  - "Did not modify COVERAGE.md: the D-02 degradation branch is tested only via a hand-written httpx double, which proves the LOGIC (exactly 2 calls, correct body shape, no loop on a second 400) but is not equivalent to exercising it against the real Groq/gpt-oss-120b provider — that limitation was already correctly documented in COVERAGE.md, 05-05-SUMMARY.md, and D-14, and 05-VERIFICATION.md classifies it as correctly characterized, not a gap"

requirements-completed: [L-02, L-03, L-06, D-01, D-02, D-03, D-05, D-09, D-10, D-11, D-12]

coverage:
  - id: D1
    description: "BriefingResponse.extrator only accepts llm, heuristico, or falha (Pydantic Literal); any other value raises ValidationError instead of being silently accepted"
    requirement: "L-02"
    verification:
      - kind: unit
        ref: "python -c one-off: typing.get_args(BriefingResponse.model_fields['extrator'].annotation) == ('llm','heuristico','falha')"
        status: pass
      - kind: unit
        ref: "python -c one-off: pytest.raises(ValidationError) constructing BriefingResponse with extrator='gpt-5-turbo'"
        status: pass
    human_judgment: false
  - id: D2
    description: "A stale cache row whose extrator value is outside the enum (e.g. written by a future refactor) becomes a cache miss and triggers fresh collection (200, origem: novo) instead of a 500 or a false extrator: falha, thanks to the 05-08 cache-row guard"
    requirement: "L-02"
    verification:
      - kind: integration
        ref: "test_smoke.py#test_cache_com_extrator_fora_da_enumeracao_vira_miss"
        status: pass
    human_judgment: false
  - id: D3
    description: "The cache-upgrade rule (D-09) is locked in both directions: a heuristico row is invalidated when the LLM becomes available, and an llm row survives when the key is later removed"
    requirement: "D-09"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_cache_heuristico_vira_miss_quando_llm_disponivel"
        status: pass
      - kind: unit
        ref: "test_smoke.py#test_cache_llm_sobrevive_quando_llm_indisponivel"
        status: pass
    human_judgment: false
  - id: D4
    description: "Prompt-injection delimiter anti-forgery (D-11) is locked: a page whose text and title print the literal DELIM_INICIO/DELIM_FIM strings ends up with exactly one legitimate occurrence of each in the user message, while the surrounding forged content survives as inert text"
    requirement: "D-11"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_montar_mensagens_remove_delimitador_forjado"
        status: pass
    human_judgment: false
  - id: D5
    description: "The D-02 json_schema degradation branch is locked against a hand-written httpx.Client double: a 400-then-200 script yields a valid Briefing after exactly 2 calls (second body has only model/messages/temperature, same messages as the first call); a 400-then-400 script raises LLMError mentioning 400 after exactly 2 calls, proving the branch never loops (D-03)"
    requirement: "D-02"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_degradacao_json_schema_faz_exatamente_uma_segunda_chamada"
        status: pass
      - kind: unit
        ref: "test_smoke.py#test_segundo_400_de_json_schema_vira_llmerror"
        status: pass
    human_judgment: true
    rationale: "These tests prove the branch's LOGIC against a double, not against the real provider — gpt-oss-120b does not produce the HTTP 400 that triggers this branch, a limit already documented in COVERAGE.md/05-05-SUMMARY.md/D-14 and classified by 05-VERIFICATION.md as correctly characterized, not a gap. A human should confirm this residual limit remains accurately described before shipping."
  - id: D6
    description: "pytest -q runs offline, no API key, no network, 16 tests green, in under 3s; briefings.db is never opened or altered by the suite"
    verification:
      - kind: unit
        ref: "pytest -q -> 16 passed in 0.42-0.45s across multiple runs; git status --porcelain briefings.db empty after every run"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-08-27
status: complete
---

# Phase 5 Plan 09: WR-01/WR-02 Gap Closure Summary

**`BriefingResponse.extrator` closed to a Pydantic `Literal["llm", "heuristico", "falha"]` (WR-01), plus 6 new offline tests locking the cache-upgrade rule (D-09, both directions), the delimiter anti-forgery (D-11), and the D-02 json_schema degradation branch including its no-loop guarantee (D-03) — suite grows from 10 to 16, all green, no network, no API key.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-08-27T00:06:00-03:00 (approx.)
- **Completed:** 2026-08-27T00:15:00-03:00 (approx.)
- **Tasks:** 3
- **Files modified:** 2 (`app/schemas.py`, `test_smoke.py`)

## Accomplishments
- `BriefingResponse.extrator` is no longer a plain `str` — it's `Literal["llm", "heuristico", "falha"]`, matching the exact declaration style of `Briefing.confianca` two lines below. SPEC §8's enum is now a Pydantic-enforced invariant, not a convention that happened to hold.
- Closing that enum introduces a new failure mode (a stale cache row with an out-of-enum `extrator` now raises `ValidationError` at `BriefingResponse` construction) — verified safe because the 05-08 cache-row guard converts that into a cache miss (200, `origem: novo`) instead of a 500. A dedicated test (`test_cache_com_extrator_fora_da_enumeracao_vira_miss`) proves both halves of this at once: the enum is enforced, and the guard catches the resulting exception.
- The `db.buscar` cache-upgrade rule (D-09) is now locked in both directions: `heuristico` rows become a miss when the LLM is available, and `llm` rows are *not* invalidated when the key is later removed — closing the exact "an `or` flipped to `and`" regression risk `05-REVIEW.md` called out.
- `_montar_mensagens`'s delimiter anti-forgery (D-11, injection-mitigation layer 2 of 3) is now locked: a page whose text and title print the literal `DELIM_INICIO`/`DELIM_FIM` strings ends up with exactly one legitimate occurrence of each in the outgoing user message, and the forged content survives as inert text (not censored, just de-fanged).
- The D-02 `_SemJsonSchema` degradation branch is now locked against a hand-written `httpx.Client` double (no new dependency): a 400-then-200 script proves exactly one extra call happens, with the correct body shape and identical messages across both calls; a 400-then-400 script proves the branch does not loop (`LLMError` after exactly 2 calls, per D-03).
- Suite grows from 10 to 16 tests, all offline, no API key, no network, in ~0.45s.

## Task Commits

Each task followed RED -> GREEN (Task 1) or straight-to-green regression-lock (Tasks 2-3, by design — see Decisions):

1. **Task 1: Fechar a enumeracao de extrator em Literal (WR-01)** - `4463849` (test, RED — confirmed failing before the fix), `07cf5c2` (feat, GREEN)
2. **Task 2: Travar a regra de upgrade de cache (D-09) e a anti-forja de delimitador (D-11)** - `4a1bff5` (test — passed immediately, no production change)
3. **Task 3: Travar o galho de degradacao de saida estruturada (D-02) com httpx dublado** - `df57746` (test — passed immediately, no production change)

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `app/schemas.py` - `BriefingResponse.extrator` annotation changed from `str` to `Literal["llm", "heuristico", "falha"]`; `description` text updated to name all three values. Single-line diff; BOM preserved.
- `test_smoke.py` - 6 new tests (`test_cache_com_extrator_fora_da_enumeracao_vira_miss`, `test_cache_heuristico_vira_miss_quando_llm_disponivel`, `test_cache_llm_sobrevive_quando_llm_indisponivel`, `test_montar_mensagens_remove_delimitador_forjado`, `test_degradacao_json_schema_faz_exatamente_uma_segunda_chamada`, `test_segundo_400_de_json_schema_vira_llmerror`); two small hand-written test doubles (`_RespostaFalsa`, `_ClienteFalso`) for the `httpx.Client` degradation path; imports extended with `json`, `extractor` module, `LLMError`, `DELIM_FIM`, `DELIM_INICIO`. BOM preserved.

## Decisions Made
- Task 1 was executed as genuine RED-GREEN TDD: the new test was run and observed failing (`origem == "cache"` instead of `"novo"`) against the unmodified `str`-typed field, proving the fix — not the test's construction — closes the gap.
- Tasks 2 and 3 are intentionally regression-lock tests, not bug fixes: the plan is explicit that D-09, D-11, and D-02's degradation logic were already correctly implemented in `app/db.py` and `app/extractor.py`; the only gap was the *absence of persisted test coverage* (WR-02). All 5 tests in these tasks passed on first run with zero production-code edits, confirmed by `git diff --stat -- app/ requirements.txt` being empty after each task.
- Did not touch `COVERAGE.md`: Task 3's httpx double proves the D-02 branch's logic, not verification against the real Groq provider (`gpt-oss-120b` does not produce the HTTP 400 that triggers this branch). That limit was already accurately documented before this plan and remains accurate after it — changing `COVERAGE.md` would have overstated what Task 3 proves.

## Deviations from Plan

None - plan executed exactly as written. Every acceptance-criteria command in each task's `<acceptance_criteria>` block was run verbatim and passed, including the BOM-preservation checks, the `git diff` emptiness checks for `app/main.py`/`app/db.py`/`app/extractor.py`/`requirements.txt`/`COVERAGE.md`, the AST-based test-name checks (via `utf-8-sig` per the file's BOM), and the `git status --porcelain briefings.db` check confirming the real database was never touched.

---

**Total deviations:** 0
**Impact on plan:** None — no scope creep, no auto-fixes needed.

## Must-Haves Verification (honest accounting)

**Truths (all 5 verified):**
1. `BriefingResponse.extrator` only accepts `llm`/`heuristico`/`falha`; an out-of-enum value from an old cache row becomes a miss and forces recollection, never a 500 — VERIFIED (`test_cache_com_extrator_fora_da_enumeracao_vira_miss`; also confirmed the pre-fix test failed as `origem: cache`, proving the fix is load-bearing).
2. The cache extrator-upgrade rule is locked in both directions: a `heuristico` row with the LLM available becomes a miss, and an `llm` row without the LLM keeps serving — VERIFIED (`test_cache_heuristico_vira_miss_quando_llm_disponivel`, `test_cache_llm_sobrevive_quando_llm_indisponivel`).
3. A page that prints the delimiter itself cannot close the untrusted-data block: the untrusted content in the user message contains exactly one opening and one closing delimiter — VERIFIED (`test_montar_mensagens_remove_delimitador_forjado`, scoped to message index 1 as the plan specifies).
4. The structured-output degradation branch makes exactly one second call to the provider and never loops: a second 400 becomes `LLMError` — VERIFIED (`test_degradacao_json_schema_faz_exatamente_uma_segunda_chamada`, `test_segundo_400_de_json_schema_vira_llmerror`). Flagged honestly: this proves the branch's logic against a hand-written double, not against the real Groq provider — a residual, already-documented limit (see `coverage.D5.rationale` above and `COVERAGE.md`).
5. `pytest -q` runs offline, no API key, no network, 16 tests green — VERIFIED, consistently ~0.42-0.45s across multiple runs; no test opens a socket or touches `briefings.db` (confirmed via `git status --porcelain briefings.db` being empty after every run).

**Artifacts (all 7 present):**
- `app/schemas.py::BriefingResponse.extrator` (`Literal["llm", "heuristico", "falha"]`) — present
- `test_smoke.py::test_cache_com_extrator_fora_da_enumeracao_vira_miss` — present
- `test_smoke.py::test_cache_heuristico_vira_miss_quando_llm_disponivel` — present
- `test_smoke.py::test_cache_llm_sobrevive_quando_llm_indisponivel` — present
- `test_smoke.py::test_montar_mensagens_remove_delimitador_forjado` — present
- `test_smoke.py::test_degradacao_json_schema_faz_exatamente_uma_segunda_chamada` — present
- `test_smoke.py::test_segundo_400_de_json_schema_vira_llmerror` — present

**Key links:** all three confirmed by direct execution and code reading:
- The 05-08 cache-row guard (`try: ... except (ValidationError, TypeError): pass` around `BriefingResponse` construction in `gerar_briefings`) is exactly what makes closing `extrator` to a `Literal` safe — proven behaviorally by `test_cache_com_extrator_fora_da_enumeracao_vira_miss` passing (200, `origem: novo`) rather than the request 500ing.
- The D-09 tests monkeypatch `db.DB_PATH` to `tmp_path` before any call to the module; `briefings.db` is never opened or altered (confirmed via `git status --porcelain briefings.db` staying empty).
- The D-02 tests double `httpx.Client` inside `app.extractor`'s namespace; no socket is opened and the API key comes in via the constructor argument (`api_key="chave-de-teste-sem-valor"`), never from the environment.

## Known Stubs

None. No hardcoded empty values, placeholder text, or unwired data sources were introduced.

## Issues Encountered

None. All three tasks' acceptance criteria passed on first implementation attempt.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **WR-01 closed:** SPEC §8's enum is now a Pydantic-enforced invariant; closing it did not open a 500 route — the 05-08 guard converts the old row into a miss.
- **WR-02 closed:** the three routes `05-REVIEW.md` named (D-09, D-02, D-11) all have persisted, offline, deterministic test coverage. A regression in any of them will now fail the suite instead of shipping silently.
- Together with `05-08` (which closed the `L-02` blocker), this closes every gap `05-VERIFICATION.md` and `05-REVIEW.md` identified for Phase 5. No item from either report remains open.
- The suite remains offline, no API key, no network, fast (~0.45s for 16 tests); `briefings.db` is never opened by any test.
- No new dependency, no DDL, `COVERAGE.md` and its already-documented residual limits (D-02 branch not exercised against the real provider, per-URL latency only order-of-magnitude) remain exact and untouched.
- `app/db.py`, `app/extractor.py`, `app/config.py`, `app/main.py`, `static/index.html`, `.env.example`, and `requirements.txt` are all untouched by this plan, confirmed via `git diff --stat` after every task.

## Self-Check: PASSED

- `app/schemas.py` exists and contains `Literal["llm", "heuristico", "falha"]` for `extrator` — FOUND (verified by direct read and the `typing.get_args` acceptance check).
- `test_smoke.py` exists and contains all 6 new test functions — FOUND (verified via AST parse with `utf-8-sig`, per acceptance criteria).
- Commits `4463849`, `07cf5c2`, `4a1bff5`, `df57746` all present in `git log --oneline` — FOUND.
- `pytest -q` reports `16 passed` — FOUND (re-run at self-check time, 0.45s).

---
*Phase: 05-llm*
*Completed: 2026-08-27*
