---
phase: 05-llm
fixed_at: 2026-08-27T03:55:00Z
review_path: .planning/phases/05-llm/05-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 05-llm: Code Review Fix Report

**Fixed at:** 2026-08-27T03:55:00Z
**Source review:** .planning/phases/05-llm/05-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (fix_scope: critical_warning — 1 Critical + 4 Warnings; Info findings IN-01..IN-05 out of scope, not attempted)
- Fixed: 5
- Skipped: 0

**Verification environment:** all fixes applied and verified inside an isolated git worktree
(`gsd-reviewfix/05-<pid>` branch, fast-forwarded into `main` on cleanup). `pytest -q` (16 tests)
was run after every fix and passed each time; additional ad-hoc functional scripts (not committed)
exercised the specific behavior each fix targets (SSRF host blocking, redirect revalidation,
streaming size cap, sqlite connection closure via `os.remove` on Windows, corrupted-row-as-miss,
rate-limit 429 threshold). Results below are reproducible by re-running `pytest -q` from `main`
after this branch is merged.

## Fixed Issues

### CR-01: SSRF — server fetches attacker-chosen URLs with no network restriction, no auth, no rate limit

**Files modified:** `app/fetcher.py`
**Commit:** `b57342a`
**Applied fix:** Added `_host_e_publico()` (resolves the host via `socket.getaddrinfo` and rejects
private/loopback/link-local/multicast/reserved/unspecified addresses — covers the
`169.254.169.254` cloud-metadata case via `is_link_local`) and `_validar_url_publica()`, called
before the robots.txt fetch and before every outbound HTTP request in `buscar_html`. Switched
`httpx.Client` to `follow_redirects=False` and added a manual redirect loop (capped at
`MAX_REDIRECTS = 5`) that re-validates the resolved host of every hop before following it — closing
the "even an allow/deny-list would need to check every hop" gap the reviewer called out. Also
disabled `follow_redirects` on the `pode_raspar()` robots.txt request for the same reason (its host
is already validated by the caller, but a 3xx there could otherwise point off-host to a private
address). Verified functionally: `_host_e_publico` correctly rejects `localhost`, `127.0.0.1`,
`169.254.169.254`, and `10.0.0.1`; `_validar_url_publica` raises `FetchError` for the metadata
address.
Rate limiting / auth (the second half of the reviewer's fix suggestion) is addressed separately
under WR-04 below, per the dedicated finding for that concern.

### WR-01: Size cap enforced after the full response body is already in memory

**Files modified:** `app/fetcher.py`
**Commit:** `4dcdc7e`
**Applied fix:** Rewrote `buscar_html` to use `client.stream("GET", url)` and `resp.iter_bytes()`,
checking accumulated size against `MAX_BYTES` on every chunk and raising `FetchError` mid-download
instead of after buffering the entire body via `.get()`. This was combined with the redirect-hop
walk from CR-01 (each hop is now a `client.stream()` call; only the final non-redirect response's
body is read). Also lower-cased the content-type check (`"html" not in tipo.lower()`) since the
reviewer's own fix snippet for this finding included that change. Verified functionally with a
monkeypatched `httpx.Client`/`stream` double: normal small pages decode correctly, an oversized
response is aborted mid-stream with `FetchError`, case-insensitive content-type is accepted, and a
redirect chain is followed and re-validated at each hop with excess redirects raising `FetchError`.

### WR-02: sqlite3 connections are never explicitly closed

**Files modified:** `app/db.py`
**Commit:** `5d70849`
**Applied fix:** Imported `contextlib.closing` and changed all four connection sites
(`criar_tabelas`, `buscar`, `salvar`, `listar`) from `with conectar() as conn:` to
`with closing(conectar()) as conn, conn:`, which both commits/rolls back the transaction (via the
inner `conn` context manager) and explicitly closes the connection/file handle (via `closing`).
Verified functionally on Windows: after `db.criar_tabelas()` / `salvar()` / `buscar()` / `listar()`
against a temp DB file, `os.remove()` on that file succeeded without `PermissionError` — proof the
connection's file handle was released, not left open pending GC.

### WR-03: `db.buscar` has no defense against a corrupted cache row, unlike a schema-shape-drifted one

**Files modified:** `app/db.py`
**Commit:** `6e50440`
**Applied fix:** Wrapped `datetime.fromisoformat(row["coletado_em"])` in `try/except ValueError:
return None` and `json.loads(row["briefing"])` in `try/except json.JSONDecodeError: return None`,
matching the "corrupted/stale row = cache miss, recollect" policy the code already documents for
schema-shape drift (D-10) — instead of letting the exception propagate to `main.py`'s broad
`except Exception:` and produce a terminal `"falha"` briefing. Verified functionally: rows with a
malformed `coletado_em` string and with invalid JSON in `briefing` both now return `None` from
`db.buscar()` (cache miss) rather than raising.

### WR-04: No rate limiting or authentication on an endpoint that triggers billed LLM calls

**Files modified:** `app/main.py`
**Commit:** `8ec1427`
**Applied fix:** Added an in-memory, per-IP sliding-window rate limiter (`_checar_rate_limit`,
20 requests/minute/IP, `threading.Lock`-guarded module-level state) wired in as a FastAPI
`Depends()` dependency on `POST /api/briefings`, raising `HTTPException(429)` once the caller's IP
exceeds the window. Chose a lightweight rate limit over an API-key requirement to avoid breaking
the existing unauthenticated single-page UI (`static/index.html`) and to avoid touching
`.env.example` (blocked by the tool-permission layer per IN-01 / orchestrator note — adding a new
required env var there wasn't attempted). This is explicitly a minimal, single-process abuse
control (documented as such in the code comment) — it does not replace an API gateway or per-key
quota if the service is later deployed behind multiple workers/processes. Verified functionally: 25
sequential `POST /api/briefings` calls from the same TestClient returned `200` for the first 20 and
`429` for the remaining 5, confirming the threshold and 429 response.

## Skipped Issues

None — all 5 in-scope findings (CR-01, WR-01, WR-02, WR-03, WR-04) were fixed and verified.

Info-tier findings (IN-01 through IN-05) were out of scope for this run (`fix_scope:
critical_warning`) and were not attempted. Notably IN-01 (`.env.example` unreviewable) remains
blocked by the same tool-permission restriction noted in REVIEW.md and by this orchestrator run's
explicit instruction not to touch that file.

---

_Fixed: 2026-08-27T03:55:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
