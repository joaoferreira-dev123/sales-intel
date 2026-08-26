---
phase: 05-llm
reviewed: 2026-08-26T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - app/config.py
  - app/db.py
  - app/extractor.py
  - app/fetcher.py
  - app/main.py
  - app/schemas.py
  - static/index.html
  - test_smoke.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-08-26T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8 (`.env.example` could not be read — blocked by the reviewing agent's own filesystem permission settings, unrelated to the code under review; its contents were not assessed)
**Status:** issues_found

## Summary

Reviewed the LLM-extraction phase: `app/config.py`, `app/db.py`, `app/extractor.py`, `app/fetcher.py`, `app/main.py`, `app/schemas.py`, `static/index.html`, and `test_smoke.py`. The design decisions called out in phase context (D-01 through D-14, L-03/L-04/L-05) are implemented faithfully: `httpx` is used directly with no SDK, the single degradation retry is gated correctly on HTTP 400 + `response_format`/`json_schema` in the body, no retry happens on timeout/network/5xx, degradation is reported through the separate `degradado` field with `str(exception)` only interpolated for authored `LLMError` instances, the cache-upgrade rule lives entirely in `db.py::buscar`'s read path with no schema change, the prompt is truncated before injection-mitigation delimiters are applied, and `Briefing(**dados)` validates the provider's JSON on the way back. No SQL injection risk (all queries parameterized), no XSS in `static/index.html` (every model-controlled value is escaped via `escapar()` before insertion, and no value is ever placed inside a single-quoted attribute), and no path where the API key can reach a log, response body, exception message, or the database — the key only ever appears in the `Authorization` header of the outbound HTTP request. `test_smoke.py` never hits the network or requires a real key: URL fetching, `escolher_extrator`, and `db.buscar`/`db.salvar` are all monkeypatched, and the one test that instantiates `TestClient` without a context manager deliberately skips the startup lifespan so `briefings.db` is never touched.

The one real gap is a correctness issue: the per-URL loop in `gerar_briefings` only catches `FetchError`, not exceptions from cache deserialization or from the database write, which breaks the documented "one URL failing doesn't take down the others" guarantee and can turn a single bad cache row or DB error into a 500 for the entire batch. There are also a few quality gaps worth tightening: the `extrator` field's type doesn't enforce the SPEC's enum, and none of the three most security/correctness-critical code paths added this phase (cache-upgrade rule, JSON-schema degradation retry, prompt-injection delimiter hardening) have any test coverage.

## Critical Issues

### CR-01: Unhandled exceptions outside `FetchError` crash the whole batch, not just one URL

**File:** `app/main.py:118-136`
**Issue:** The per-URL loop in `gerar_briefings` wraps `buscar_html` / `extrair_texto` / `_extrair_com_fallback` / `db.salvar` in a `try` that only catches `FetchError`:
```python
try:
    html = buscar_html(url)
    titulo, texto = extrair_texto(html)
    briefing, nome_extrator, degradado = _extrair_com_fallback(url, titulo, texto)
    if nome_extrator == "falha":
        coletado_em = datetime.now(timezone.utc)
    else:
        coletado_em = db.salvar(url, briefing.model_dump(), nome_extrator)
    origem = "novo"
except FetchError as e:
    ...
```
`_extrair_com_fallback` is carefully written to never raise (broad `except Exception` at both the LLM and heuristic level), but `db.salvar(...)` is not covered by that guarantee — a `sqlite3.OperationalError` (e.g. "database is locked", which is a realistic outcome once this sync FastAPI route is hit concurrently, since SQLite serializes writers) propagates straight out of the loop. The same is true of the cache-read path a few lines above (`app/main.py:110`, `Briefing(**dados)`): if a row in `briefings.db` was written by an earlier version of the `Briefing` schema (a near-certainty as the project gains more phases) and is now missing a field the current schema requires, `ValidationError` is raised there too, uncaught.

Either failure aborts the entire `/api/briefings` request with an unhandled-exception 500, discarding the `resultados` already computed for *other* URLs in the same batch. This directly contradicts the function's own documented contract: "Um link que falha nao derruba os outros: cada URL e tratada de forma independente" (`app/main.py:93-94`), a guarantee that is explicitly unit-tested for extractor failures (`test_extrator_que_falha_nao_derruba_a_requisicao`) but not for DB/cache failures.

**Fix:** Widen the per-URL guard to cover storage/deserialization failures too, and degrade that single URL to a `falha` result instead of letting the exception escape the loop:
```python
try:
    html = buscar_html(url)
    titulo, texto = extrair_texto(html)
    briefing, nome_extrator, degradado = _extrair_com_fallback(url, titulo, texto)
    if nome_extrator == "falha":
        coletado_em = datetime.now(timezone.utc)
    else:
        coletado_em = db.salvar(url, briefing.model_dump(), nome_extrator)
    origem = "novo"
except FetchError as e:
    briefing = Briefing(empresa=url, resumo=f"Nao foi possivel coletar esta pagina. {e}", confianca="baixa")
    coletado_em = datetime.now(timezone.utc)
    origem = "novo"
    nome_extrator = "falha"
    degradado = None
except Exception:
    briefing = Briefing(empresa=url, resumo="Nao foi possivel gerar o briefing para este link.", confianca="baixa")
    coletado_em = datetime.now(timezone.utc)
    origem = "novo"
    nome_extrator = "falha"
    degradado = None
```
and similarly wrap the cache-hit branch's `Briefing(**dados)` (`app/main.py:110`) in a `try/except (ValidationError, TypeError)` that falls through to treat the row as a cache miss instead of crashing the request.

## Warnings

### WR-01: `BriefingResponse.extrator` does not enforce the SPEC's closed enum

**File:** `app/schemas.py:58`
**Issue:** SPEC section 8 requires the `extrator` value to be exactly one of `llm` / `heuristico` / `falha`, and the whole design of `_extrair_com_fallback` (D-05/D-06) is built around never introducing a fourth value. The field is currently declared as a plain `str`:
```python
extrator: str = Field(description="Qual implementacao gerou: heuristico ou llm")
```
Today every call site happens to only ever assign one of the three sanctioned literals, so nothing is broken in practice, but the type gives no compile-time/runtime protection against a future code path (or a stale cache row written by a future refactor) producing an out-of-band value, and it doesn't self-document the closed set the way `Briefing.confianca` does two lines below with `Literal["alta", "media", "baixa"]`.
**Fix:**
```python
extrator: Literal["llm", "heuristico", "falha"] = Field(
    description="Qual implementacao gerou: heuristico, llm ou falha"
)
```

### WR-02: No test coverage for the three most load-bearing behaviors added this phase

**File:** `test_smoke.py` (whole file); behaviors defined in `app/db.py:41-63`, `app/extractor.py:103-238`
**Issue:** `test_smoke.py` exercises the heuristic extractor, the no-key/with-key extractor selection, and the top-level fallback-to-heuristic path, but none of the following get any direct test coverage:
- The cache-upgrade predicate in `db.py::buscar` (D-09/D-10) — no test calls `db.buscar` with `llm_disponivel=True` against a `heuristico`-tagged row to confirm it's treated as a miss, nor confirms a fresh `llm`-tagged row is *not* invalidated when the key is later removed.
- The single-retry JSON-schema degradation path in `LLMExtractor._chamar_provedor` (D-02) — no test drives a mocked 400 response containing `response_format`/`json_schema` through `httpx` (e.g. via `respx` or a monkeypatched `httpx.Client`) to confirm exactly one retry happens and that a second such failure does not loop.
- The prompt-injection hardening in `_montar_mensagens` (D-11) — no test asserts that a page whose text contains the literal delimiter strings has them stripped before being placed in the user message.

These are exactly the code paths the phase context flags as most important to get right, and a regression in any of them (e.g. an accidental `or` flipped to `and` in the cache predicate, or the second `_chamar_provedor` call being reachable more than once) would currently ship undetected.
**Fix:** Add unit tests for `db.buscar`'s upgrade branch (insert a `heuristico` row directly, call `buscar(url, llm_disponivel=True)`, assert `None`), for `_montar_mensagens` (assert `DELIM_INICIO`/`DELIM_FIM` are absent from the untrusted-content span when the source text contains them), and for `_chamar_provedor`'s degradation path using a stubbed `httpx.Client.post`.

### WR-03: Double-failure branch interpolates a raw, unauthored exception into a user-facing field

**File:** `app/main.py:78-84`
**Issue:** When both the primary extractor and the heuristic fallback raise, the handler builds the response directly from the heuristic exception's `str()`:
```python
except Exception as erro_heuristico:
    briefing = Briefing(
        empresa=url,
        resumo=f"Nao foi possivel gerar o briefing. {erro_heuristico}",
        confianca="baixa",
    )
    return briefing, "falha", None
```
This is the same category of concern D-06 addresses for the `degradado` field (only interpolate `str(exception)` for messages we author) but here it's applied unconditionally to whatever `HeuristicExtractor.extrair()` happens to raise, with no `isinstance` guard. In the current code `HeuristicExtractor.extrair()` is effectively exception-free given its inputs are always `str` (so this path is realistically unreachable today), but the guard is missing, so the very next change that lets an unexpected exception type reach this branch (e.g. a future heuristic rule that can raise on malformed input) would silently start leaking raw internal error text to the vendor-facing `resumo` field with no review gate.
**Fix:** Use the same generic-phrase-only pattern already used for `degradado`:
```python
except Exception:
    briefing = Briefing(
        empresa=url,
        resumo="Nao foi possivel gerar o briefing para este link.",
        confianca="baixa",
    )
    return briefing, "falha", None
```

## Info

### IN-01: Redundant re-execution when the primary extractor is already the heuristic one

**File:** `app/main.py:58-77`
**Issue:** When no LLM key is configured, `escolher_extrator()` returns a `HeuristicExtractor`. If that call raises, the `except` block instantiates a brand-new `HeuristicExtractor()` and calls `.extrair()` again with the exact same arguments (`app/main.py:67`). Since `HeuristicExtractor.extrair` is a pure, deterministic function of its inputs, this second call is guaranteed to fail identically to the first — it's dead-weight work on every double-failure in heuristic-only mode, and it makes the two-tier "degrade to heuristic" comment slightly misleading in that specific case (there's no real second attempt, just a repeat of the first).
**Fix:** Not required to change behavior, but consider short-circuiting: if `extrator` is already a `HeuristicExtractor` instance, skip straight to the `falha` branch instead of re-invoking it.

### IN-02: `@app.on_event("startup")` is deprecated

**File:** `app/main.py:34-36`
**Issue:** `@app.on_event("startup")` has been deprecated since Starlette/FastAPI moved to the `lifespan` context-manager API; it still works but emits a deprecation warning and is a candidate for removal in a future FastAPI major version.
**Fix:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.criar_tabelas()
    yield

app = FastAPI(..., lifespan=lifespan)
```
Note this would also require updating `test_smoke.py`'s deliberate `TestClient(main.app)` (no `with`) trick, since it currently relies on the startup event *not* firing without a context manager — worth keeping in mind together, not fixing in isolation.

---

_Reviewed: 2026-08-26T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
