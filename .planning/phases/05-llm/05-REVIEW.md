---
phase: 05-llm
reviewed: 2026-08-27T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - .env.example
  - .gsd/dispatch-isolation-sentinel.json
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
  warning: 4
  info: 5
  total: 10
status: issues_found
---

# Phase 05-llm: Code Review Report

**Reviewed:** 2026-08-27T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

This phase adds the LLM extractor, the extractor fallback ladder, and the fetch/scrape
pipeline that feeds it. The prompt-injection mitigation in `app/extractor.py` (delimiter
anti-forgery, schema-locked system prompt, Pydantic re-validation) and the "never leak a
third-party exception string to the seller" discipline (D-06) in `app/main.py` are both
genuinely well executed and hold up under adversarial reading — I could not break the
delimiter stripping, the `_SemJsonSchema` degrade-once contract, or the message-authoring
rule.

The main gap is on the *fetch* side, not the *extraction* side: `app/fetcher.py` and
`app/main.py` let any anonymous caller force the server to issue outbound HTTP requests to
an arbitrary attacker-chosen URL, with no restriction on private/internal address ranges and
no rate limiting. That is a classic SSRF exposure and is the one Critical finding below.
Several smaller robustness gaps (unbounded download-before-size-check, unclosed sqlite
connections, an inconsistency between how `db.buscar` handles schema-shape drift vs.
outright corrupt rows) round out the Warnings. `.env.example` could not be read — the tool
permission layer blocked all read attempts against it (Read, Bash `cat`, Grep all denied) —
so it is listed as reviewed-but-unverified rather than silently skipped.

## Critical Issues

### CR-01: SSRF — server fetches attacker-chosen URLs with no network restriction, no auth, no rate limit

**File:** `app/fetcher.py:30-76`, `app/main.py:100-146`

**Issue:** `POST /api/briefings` accepts up to 10 URLs from an unauthenticated caller
(`app/schemas.py:71`, `BriefingRequest.urls: list[HttpUrl]`) and passes each straight into
`buscar_html()`, which does `httpx.Client(follow_redirects=True).get(url)`
(`app/fetcher.py:57-63`) and, before that, `pode_raspar()` does the same for the derived
`robots.txt` URL (`app/fetcher.py:36-42`). `HttpUrl` validation only constrains the scheme
to http/https and the general URL shape — it does not block loopback, link-local, or
RFC1918 private addresses, cloud metadata endpoints (`169.254.169.254`), or internal
hostnames. Since `follow_redirects=True` is set on both requests, even a URL-based
allow/deny-list would additionally need to check every hop, not just the initial host.

Combined with the complete absence of authentication or rate limiting on this endpoint
(`app/main.py:100`, `@app.post("/api/briefings")` has no dependency, no API key check), any
anonymous network caller can use this service as an open SSRF proxy against whatever network
it is deployed on — e.g. `http://169.254.169.254/latest/meta-data/iam/security-credentials/`
on a cloud host, or `http://localhost:<internal-port>/admin` on the deployment box. The
`pode_raspar()` "fail open on any exception" behavior (`app/fetcher.py:46-47`) means a
request that errors against an internal host (connection refused, TLS error, etc.) is
treated as "robots allows it" and the real fetch proceeds anyway — the robots check adds no
SSRF protection.

**Fix:** Resolve and validate the target host before connecting, reject private/loopback/
link-local/multicast ranges and the cloud metadata address, and re-validate after each
redirect hop (or disable `follow_redirects` and validate manually per hop):

```python
import ipaddress
import socket

def _host_e_publico(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for family, *_rest, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False
    return True

def buscar_html(url: str) -> str:
    host = urlparse(url).hostname
    if not host or not _host_e_publico(host):
        raise FetchError("Este endereco nao pode ser coletado.")
    if not pode_raspar(url):
        raise FetchError("O robots.txt do site nao permite acesso automatizado.")
    with httpx.Client(timeout=TIMEOUT, follow_redirects=False, ...) as client:
        resp = client.get(url)
        # follow redirects manually, re-validating host at each hop
```

Also add basic abuse controls to `POST /api/briefings` (API key, IP-based rate limit, or
both) — without them, the SSRF surface (and the LLM cost-amplification noted in WR-04) is
reachable by anyone who can send an HTTP request to this service.

## Warnings

### WR-01: Size cap enforced after the full response body is already in memory

**File:** `app/fetcher.py:57-74`

**Issue:** `MAX_BYTES` is meant to keep a single scrape from consuming unbounded memory
("pagina maior que isso quase sempre e lixo"), but the check happens *after*
`client.get(url)` has already downloaded the entire body into `resp.content`
(`app/fetcher.py:62-73`). httpx does not cap response size on `.get()`, so a malicious or
misbehaving server (trivially reachable given CR-01 has no auth) can send an arbitrarily
large body and force the process to buffer all of it before the 3 MB check ever runs,
defeating the intended cap.

**Fix:** Stream the response and abort once the cap is exceeded:

```python
with client.stream("GET", url) as resp:
    resp.raise_for_status()
    tipo = resp.headers.get("content-type", "")
    if "html" not in tipo.lower():
        raise FetchError(f"O endereco nao devolveu HTML (veio {tipo or 'sem tipo'}).")
    total = 0
    chunks = []
    for chunk in resp.iter_bytes():
        total += len(chunk)
        if total > MAX_BYTES:
            raise FetchError("Pagina grande demais.")
        chunks.append(chunk)
    html_bytes = b"".join(chunks)
```

### WR-02: sqlite3 connections are never explicitly closed

**File:** `app/db.py:21-24, 27-38, 41-63, 66-80, 83-91`

**Issue:** Every function opens a fresh connection with `conectar()` and wraps it in
`with conectar() as conn:` (e.g. `app/db.py:28`, `:47`, `:68`, `:85`). `sqlite3.Connection`
used as a context manager only commits/rolls back the transaction on `__exit__` — it does
**not** close the connection or its underlying file handle. The code relies on CPython's
reference-counting GC to close the connection promptly once `conn` goes out of scope; under
PyPy or any GC implementation without immediate refcounting, or under any future change that
keeps a reference alive longer than expected, this would leak file descriptors.

**Fix:** Nest an explicit close, or use `contextlib.closing`:

```python
from contextlib import closing

def criar_tabelas() -> None:
    with closing(conectar()) as conn, conn:
        conn.execute(...)
```

### WR-03: `db.buscar` has no defense against a corrupted cache row, unlike a schema-shape-drifted one

**File:** `app/db.py:56, 63`, `app/main.py:118-146`

**Issue:** `app/main.py:141` explicitly narrows its cache-read exception handling to
`(ValidationError, TypeError)` and documents why (D-10: an old-schema row is stale data, not
an error, so it should fall through to a fresh recollect rather than blow up the whole
request). But `db.buscar()` itself can raise *before* that guard is ever reached:
`datetime.fromisoformat(row["coletado_em"])` (`app/db.py:56`) and `json.loads(row["briefing"])`
(`app/db.py:63`) both raise uncaught (`ValueError` / `json.JSONDecodeError`) if the stored
row is malformed. Those exceptions propagate past the narrow `except (ValidationError,
TypeError)` in `main.py` and are instead caught by the broad `except Exception:` at
`app/main.py:177`, which produces a terminal `"falha"` briefing for that URL — the opposite
of the documented "stale/bad cache row => miss => recollect" policy the code otherwise
follows carefully for the schema-drift case.

**Fix:** Treat decode failures the same way as a missing row (i.e. as a cache miss) inside
`db.buscar` itself:

```python
    if row is None:
        return None
    try:
        coletado_em = datetime.fromisoformat(row["coletado_em"])
    except ValueError:
        return None
    if datetime.now(timezone.utc) - coletado_em > VALIDADE:
        return None
    if llm_disponivel and row["extrator"] == "heuristico":
        return None
    try:
        briefing = json.loads(row["briefing"])
    except json.JSONDecodeError:
        return None
    return briefing, row["extrator"], coletado_em
```

### WR-04: No rate limiting or authentication on an endpoint that triggers billed LLM calls

**File:** `app/main.py:100-146`

**Issue:** `POST /api/briefings` accepts up to 10 URLs per call, and — whenever
`LLM_API_KEY` is configured — each URL that is not already cached triggers a billed call to
the configured LLM provider (`app/extractor.py:158-213`). There is no per-caller rate limit,
API key, or quota on this endpoint. Anyone who can reach the service can drive unbounded LLM
spend simply by posting distinct/`forcar_atualizacao=true` URLs in a loop. This is
independent of CR-01 (SSRF); even once outbound fetch targets are restricted to public
hosts, cost-abuse via arbitrary public URLs remains open.

**Fix:** Add a lightweight rate limit (per-IP or API-key based) in front of
`gerar_briefings`, or require an API key header validated against a configured value before
the extractor path runs.

## Info

### IN-01: `.env.example` could not be reviewed

**File:** `.env.example`

**Issue:** All three tools attempted against this file (`Read`, `Bash cat`, `Grep`) were
denied by the harness's own permission classifier ("Permission to read ... has been denied" /
"Permission for this action was denied by the Claude Code auto mode classifier"), presumably
because it pattern-matches as a secrets-bearing filename. This is a tool-permission
restriction, not a finding about the file's content — the file is listed as reviewed for
scope-tracking purposes but its contents are unverified. Given `app/config.py` documents
four LLM-related env vars (`LLM_API_KEY`, `LLM_MODELO`, `LLM_MAX_CHARS`, `LLM_BASE_URL`), a
human (or an agent with broader file-read permissions) should confirm `.env.example` lists
placeholder values for exactly those four and contains no real credentials.

**Fix:** Re-run this check with a permission profile that allows reading `.env.example`
(not `.env`), or have a human confirm its contents directly.

### IN-02: Manual HTML-escaping helper doesn't escape single quotes

**File:** `static/index.html:110-113`

**Issue:** `escapar()` only escapes `& < > "`:
```js
function escapar(s) {
  return String(s ?? '').replace(/[&<>"]/g, c =>
    ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' }[c]));
}
```
Every current call site places the escaped value in a text node or a double-quoted
attribute, so this isn't exploitable today. But `render()` (`static/index.html:90-108`)
interpolates model output — content ultimately derived from third-party scraped pages
(`empresa`, `resumo`, `degradado`, list items) — into a raw template string assigned via
`innerHTML`. If a future edit places any of these values inside a single-quoted attribute,
this becomes an XSS vector with no other layer of defense.

**Fix:** Escape `'` as `&#39;` as well, or switch to building nodes via `textContent`/
`setAttribute` instead of string-templated `innerHTML`.

### IN-03: Content-type check is case-sensitive

**File:** `app/fetcher.py:69-71`

**Issue:** `if "html" not in tipo:` compares the raw header value without lowercasing it.
An (unusual but valid) server that sends `Content-Type: TEXT/HTML` would be incorrectly
rejected as non-HTML.

**Fix:** `if "html" not in tipo.lower():`

### IN-04: `/api/historico` accepts unbounded/negative `limite` with no validation

**File:** `app/main.py:207-210`

**Issue:** `def historico(limite: int = 50)` passes `limite` straight into
`db.listar(limite)` → `"... LIMIT ?"` (`app/db.py:83-91`). SQLite treats a negative `LIMIT`
as "no limit," so `?limite=-1` returns the entire table instead of erroring or being
clamped. Not a security issue on its own (the columns returned are non-sensitive), but it's
a missing input-validation guard on a public parameter.

**Fix:** `limite: int = Query(50, ge=1, le=500)`.

### IN-05: FastAPI startup wired via the deprecated `on_event` API

**File:** `app/main.py:41-43`

**Issue:** `@app.on_event("startup")` has been deprecated by FastAPI in favor of the
`lifespan` context-manager parameter to `FastAPI(...)`. It still works but will eventually
be removed, and newly-written code shouldn't introduce more usage of a deprecated API.

**Fix:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.criar_tabelas()
    yield

app = FastAPI(..., lifespan=lifespan)
```

---

_Reviewed: 2026-08-27T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
