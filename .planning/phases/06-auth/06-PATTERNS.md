# Phase 6: Auth — Pattern Map

**Mapped:** 2026-08-27
**Files analyzed:** 10 (new/modified artifacts listed in prompt)
**Analogs found:** 9 / 10 (1 has no direct analog — noted below with nearest structural neighbour)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/auth.py` (hash + sessão) | service/utility | CRUD (hash compute, token issue/validate) | `app/db.py` (connection/SQL pattern) + `app/fetcher.py` (stateless pure-function utility style) | role-match (no service module precedent; closest is db.py for persistence half, fetcher.py for pure-function half) |
| `usuarios` / `sessoes` tables + `briefings.owner` column | migration (in `db.py`) | CRUD | `app/db.py:28-42` (`criar_tabelas`, `CREATE TABLE IF NOT EXISTS`) | exact |
| `schemas.py` additions (`LoginRequest`, `LoginResponse`, `Usuario`) | model | request-response | `app/schemas.py:68-74` (`BriefingRequest`), `:50-66` (`BriefingResponse`) | exact |
| `usuario_atual` / `exigir_admin` dependencies | middleware | request-response | `app/main.py:55-70` (`_checar_rate_limit`) | exact |
| `POST /api/auth/login`, `GET /api/auth/me`, `GET /api/admin/usuarios`, logout | route/controller | request-response | `app/main.py:132-137` (`gerar_briefings` route decl.), `:78-82` (`health`, plain GET) | exact |
| Guards added to `/health`, `POST /api/briefings`, `GET /api/historico`, `GET /`, `/static/*` | route (modification) | request-response | `app/main.py:132-136` (`dependencies=[Depends(_checar_rate_limit)]`) | exact |
| Owner-filtered `db.listar`/history read | service (modification) | CRUD | `app/db.py:102-110` (`listar`), `app/db.py:45-82` (`buscar`, D-09 filtering-on-read precedent) | exact |
| Login screen + admin area in `static/index.html` | component (vanilla JS) | request-response | `static/index.html:53-113` (existing `btn.onclick` fetch flow, `render()`, `escapar()`) | exact |
| New tests in `test_smoke.py` | test | CRUD + request-response | `test_smoke.py:210-232` (`tmp_path` DB isolation), `:56-86` (`TestClient` route test) | exact |
| First-admin bootstrap/seed from env | config/utility | batch (startup, one-shot) | `app/config.py:22-25` (`llm_api_key()` env read), `app/main.py:73-75` (`@app.on_event("startup") inicializar()`) | role-match (no seed-script precedent; nearest neighbour is startup hook + env-read function) |

## Pattern Assignments

### `app/auth.py` (new module — service/utility, CRUD + stateless helpers)

**No direct analog module exists.** Nearest structural neighbours: `app/db.py` for the persistence half (session table CRUD) and `app/fetcher.py`/`app/config.py` for the pure-function half (hashing, token generation reading no external state except `secrets`/`hashlib`).

**Module docstring convention** (mirror `app/db.py:1-10` and `app/config.py:1-17`): explain purpose + WHY a decision was made, in Portuguese, referencing the decision code (e.g. D-15, D-16).

**Imports pattern** to follow (`app/db.py:12-16`):
```python
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
```
For `auth.py`, the stdlib set is `hashlib`, `hmac`, `secrets`, plus `from . import db` for persistence calls — no third-party imports (L-06/D-15/D-16 forbid new deps).

**Hash function shape** — model after the plain, typed, single-purpose functions in `app/db.py:85-99` (`salvar`) and `app/config.py:22-25` (`llm_api_key`): a function per operation, explicit return type, no classes unless a Protocol is genuinely needed (no Protocol precedent applies here — `extractor.py`'s `Extractor` Protocol is for pluggable strategies, not applicable to a single hashing algorithm).

```python
# Pattern to mirror (structure only, not exact auth code):
def gerar_hash_senha(senha: str) -> str:
    """Devolve string autodescritiva scrypt$n$r$p$salt$hash (D-15)."""
    ...

def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """Compara em tempo constante via hmac.compare_digest (D-15)."""
    ...
```

**Session issue/validate** should reuse the exact DB-access shape from `app/db.py:22-25` (`conectar`) and `:32,51,87,104` (`with closing(conectar()) as conn, conn:`) — see Shared Patterns below for the literal snippet to copy.

---

### `usuarios` / `sessoes` tables + `briefings.owner` column (`app/db.py` modification)

**Analog:** `app/db.py:28-42` (`criar_tabelas`)

**Core pattern to copy exactly** (`app/db.py:28-42`):
```python
def criar_tabelas() -> None:
    # WR-02: `with conectar() as conn` sozinho so commita/reverte a
    # transacao — nao fecha a conexao nem o file handle. `closing()` garante
    # o fechamento explicito; o `conn` interno segue fazendo commit/rollback.
    with closing(conectar()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS briefings (
                url         TEXT PRIMARY KEY,
                briefing    TEXT NOT NULL,
                extrator    TEXT NOT NULL,
                coletado_em TEXT NOT NULL
            )
            """
        )
```
New tables (`usuarios`, `sessoes`) are added as additional `conn.execute("CREATE TABLE IF NOT EXISTS ...")` calls inside this same function, per STRUCTURE.md §"Persistent Data": *"Add table creation in `app/db.py` (within `criar_tabelas()`)"*.

**D-18 constraint — no destructive migration:** adding the `owner` column to `briefings` must NOT use a bare `ALTER TABLE briefings ADD COLUMN owner ...` blindly if it risks re-running against an existing populated table without a plan for old rows — mirror the read-time-filtering precedent at `app/db.py:74-75` (`if llm_disponivel and row["extrator"] == "heuristico": return None`), which shows the project's established policy: **schema drift is handled by filtering in the read function, not by mutating/deleting old rows.** `criar_tabelas()` uses `IF NOT EXISTS`/idempotent `ADD COLUMN` guarded by a try/except-on-duplicate-column pattern consistent with "sem DROP, sem DELETE" (D-18, inherited from D-10/T-05-36).

---

### `schemas.py` additions (model, request-response)

**Analog:** `app/schemas.py:68-74` (`BriefingRequest`) and `:50-66` (`BriefingResponse`)

**Imports pattern** (`app/schemas.py:11-14`):
```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl
```

**Core pattern to copy** — request/response DTO with `Literal` for closed enumerations (mirrors `confianca: Literal["alta","media","baixa"]` at `app/schemas.py:44-47` and `papel` = `Literal["vendedor","admin"]` per L-08):
```python
class LoginRequest(BaseModel):
    """O que o usuario envia para logar."""
    username: str
    senha: str

class Usuario(BaseModel):
    """Representacao do usuario devolvida pela API — nunca inclui senha_hash."""
    id: int
    username: str
    papel: Literal["vendedor", "admin"]
    ativo: bool
```
Docstring style matches `app/schemas.py:17-18` (one-line class docstring stating what the model represents/who reads it).

---

### `usuario_atual` / `exigir_admin` dependencies (middleware, request-response)

**Analog:** `app/main.py:55-70` (`_checar_rate_limit`) — this is the canonical, and per D-17 explicitly mandated, pattern.

**Full shape to copy** (`app/main.py:55-70`):
```python
def _checar_rate_limit(request: Request) -> None:
    """Dependency do FastAPI: levanta 429 se o IP do chamador excedeu o
    limite de requisicoes na janela atual. Chamada antes de qualquer fetch
    ou chamada de LLM."""
    ip = request.client.host if request.client else "desconhecido"
    agora = datetime.now(timezone.utc)
    limite_inferior = agora - _RATE_LIMIT_JANELA
    with _rate_limit_lock:
        historico = _requisicoes_por_ip.setdefault(ip, [])
        historico[:] = [t for t in historico if t >= limite_inferior]
        if len(historico) >= _RATE_LIMIT_MAX_REQUISICOES:
            raise HTTPException(
                status_code=429,
                detail="Muitas requisicoes deste endereco. Tente novamente em instantes.",
            )
        historico.append(agora)
```
**Attachment to a route** (`app/main.py:132-136`):
```python
@app.post(
    "/api/briefings",
    response_model=list[BriefingResponse],
    dependencies=[Depends(_checar_rate_limit)],
)
```
`usuario_atual` differs in that it is a **value-returning** dependency (needs to hand the resolved user to the route body), so it should instead be wired via `Depends(usuario_atual)` as a normal parameter (`def rota(usuario: Usuario = Depends(usuario_atual))`), not `dependencies=[...]` (which discards the return value). `exigir_admin` can compose on top of `usuario_atual` (a dependency that itself depends on another dependency — standard FastAPI, no existing precedent in this codebase but directly implied by D-17's own text: "não instalar pacote novo... mesmo padrão já usado por `_checar_rate_limit`").

**Raise-401/403 shape** mirrors the `HTTPException(status_code=..., detail=...)` call above — same class, same keyword style, same literal-Portuguese-message rule (see Shared Patterns → Error Handling).

---

### New routes: `/api/auth/login`, `/api/auth/me`, `/api/admin/usuarios`, logout (controller, request-response)

**Analog A (POST with schema + dependency):** `app/main.py:132-144` (`gerar_briefings`)
**Analog B (plain GET, no body):** `app/main.py:78-82` (`health`), `:243-246` (`historico`)

**Core pattern:**
```python
@app.get("/api/historico")
def historico(limite: int = 50) -> list[dict]:
    """Tela de admin: o que ja foi coletado."""
    return db.listar(limite)
```
New routes should follow this exact shape: one-line docstring stating who calls it and why, thin body that delegates to `db.py`/`auth.py`, explicit return type annotation, `response_model=` on Pydantic-typed responses (as done at `main.py:134`).

**Route function naming**: snake_case verbs matching the route's purpose (`gerar_briefings`, `historico`, `health`, `home`) — new ones should be e.g. `login`, `eu` or `me`, `usuarios_admin`, `logout`, staying Portuguese per CONVENTIONS.md.

---

### Guards on existing routes (modification, request-response)

**Analog:** `app/main.py:132-136` — the `dependencies=[Depends(...)]` kwarg on the decorator is the only existing mechanism for attaching a per-route guard; D-17 requires every route (including `/`, `/static/*`, `/health`) to have an **explicit** declared dependency (or an explicit, tested decision that it is intentionally public, per open question #2 — recommendation in CONTEXT.md is `/health` stays public with a renewed R-08 acceptance).

`/static/*` is mounted via `app.mount(...)` (`app/main.py:249`), not a decorated route function — there is **no existing analog** for guarding a `StaticFiles` mount in this codebase; the planner must decide whether static assets need protection at all (likely no, since `index.html` itself performs client-side auth-gated rendering, but the login page itself must be reachable unauthenticated).

---

### Owner-filtered history read (`db.listar` modification, CRUD)

**Analog:** `app/db.py:102-110` (`listar`) plus the read-time-filtering precedent at `app/db.py:74-75` (D-9's "filter in the read function, not the schema" pattern), directly cited in D-18.

**Core pattern to copy** (`app/db.py:102-110`):
```python
def listar(limite: int = 50) -> list[dict]:
    """Historico para a tela de admin."""
    with closing(conectar()) as conn, conn:
        rows = conn.execute(
            "SELECT url, extrator, coletado_em FROM briefings "
            "ORDER BY coletado_em DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [dict(r) for r in rows]
```
New signature should add an owner/role parameter and branch the SQL (still fully parameterized, never string-concatenated): admin gets the unfiltered query above; vendedor gets a variant with `WHERE owner = ?`. This mirrors the existing branch-by-flag style already used in `buscar()` (`app/db.py:74-75`: `if llm_disponivel and row["extrator"] == "heuristico": return None`).

---

### Login screen + admin area (`static/index.html`, vanilla JS)

**Analog:** `static/index.html:53-113` (existing fetch/render/escape flow)

**Fetch pattern to copy** (`static/index.html:58-82`):
```javascript
btn.onclick = async () => {
  ...
  try {
    const resp = await fetch('/api/briefings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ... })
    });
    if (!resp.ok) throw new Error('Erro ' + resp.status);
    const dados = await resp.json();
    ...
  } catch (e) {
    status.textContent = 'Falhou: ' + e.message;
  } finally {
    btn.disabled = false;
  }
};
```
Login form submit and admin-panel fetches (`/api/auth/login`, `/api/auth/me`, `/api/admin/usuarios`) should reuse this exact try/catch/finally + status-text-update shape. Session is cookie-based (D-16, `HttpOnly`), so the JS does not need to manually attach a token header — `fetch` with default `credentials: 'same-origin'` suffices, but confirm no `credentials: 'omit'` is introduced anywhere.

**Escaping helper — XSS risk flagged explicitly** (`static/index.html:110-113`):
```javascript
function escapar(s) {
  return String(s ?? '').replace(/[&<>"]/g, c =>
    ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' }[c]));
}
```
**This regex does NOT escape `'` (single quote).** It is safe today only because every interpolation in `render()`/`lista()` happens inside double-quoted HTML attributes or text nodes (`static/index.html:90-108`). Any new admin-area markup that interpolates a value inside a single-quoted attribute (e.g. `<input value='${escapar(x)}'>`) reintroduces attribute-context XSS. The planner must either (a) never use single-quoted attributes in new markup, or (b) extend `escapar()` to also map `'` → `&#39;` before the admin UI ships — CONTEXT.md's threat_seeds section names this exact gap.

**Rendering pattern** — template-literal string building + `.innerHTML =`, no DOM APIs, no framework (`static/index.html:76,86-108`) — new login/admin views must follow the same plain-template-literal style, kept inline in `index.html` per STRUCTURE.md: *"Keep inline (no separate files) to keep deployment simple."*

---

### New tests in `test_smoke.py` (test, CRUD + request-response)

**Analog A (DB isolation via tmp_path):** `test_smoke.py:210-217`
```python
def test_cache_heuristico_vira_miss_quando_llm_disponivel(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "teste.db")
    db.criar_tabelas()
    db.salvar("https://acme.com.br", {"empresa": "Acme", "resumo": "texto"}, "heuristico")
    assert db.buscar("https://acme.com.br", llm_disponivel=True) is None
```
**Analog B (route test via TestClient + monkeypatch):** `test_smoke.py:56-86`
```python
monkeypatch.setattr(main, "escolher_extrator", lambda: ExtratorQuebrado())
...
client = TestClient(main.app)
resp = client.post("/api/briefings", json={...})
assert resp.status_code == 200
```
Both patterns apply directly: auth tests need `monkeypatch.setattr(db, "DB_PATH", tmp_path / "teste.db")` + `db.criar_tabelas()` for isolation (never touch the real `briefings.db`), and `TestClient(main.app)` for route-level 401/403 assertions on `usuario_atual`/`exigir_admin`. Naming convention: `test_<comportamento_em_portugues>()`, e.g. `test_rota_admin_recusa_vendedor_com_403`. No mocking library beyond `monkeypatch` — consistent with TESTING.md's "no unittest.mock imports observed."

**Comment convention** — every non-obvious assertion is preceded by a `# D-xx:`/`# L-xx:`/`# WR-xx:` comment citing the decision it locks in (seen throughout `test_smoke.py`, e.g. lines 47-48, 98-101, 175-181). New auth tests should cite D-15/D-16/D-17/D-18 the same way.

---

### First-admin bootstrap/seed from env (D-19) — no direct analog

**Nearest neighbours:** `app/config.py:22-25` (env-read function pattern) + `app/main.py:73-75` (startup hook).

```python
# app/config.py:22-25
def llm_api_key() -> str | None:
    """Funcao, nao constante: precisa ler o ambiente em tempo de chamada
    para que o monkeypatch dos testes 1 e 2 (plano 03) funcione."""
    return os.getenv("LLM_API_KEY") or None
```
```python
# app/main.py:73-75
@app.on_event("startup")
def inicializar() -> None:
    db.criar_tabelas()
```
No script/CLI seed pattern exists anywhere in the codebase — STRUCTURE.md confirms there is no `scripts/` directory and no precedent for a standalone bootstrap script. The planner should decide (open question #5 in CONTEXT.md) between: (a) extending `inicializar()` in `app/main.py` to call an `auth.semear_admin_inicial()` function that reads `ADMIN_USERNAME`/`ADMIN_SENHA` env vars (mirrors `config.py`'s function-not-constant rule, since tests monkeypatch env vars at call time) or (b) a separate one-off script — but (a) is the closer fit to existing conventions since the only existing "run something at boot" hook is `inicializar()`.

## Shared Patterns

### DB Connection Handling
**Source:** `app/db.py:22-25`, `:32`, `:51`, `:87`, `:104`
**Apply to:** `app/auth.py` (all session-table and usuarios-table CRUD)
```python
def conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
```
```python
with closing(conectar()) as conn, conn:
    conn.execute("...", (param1, param2))
```
Always parameterized SQL (`?` placeholders, never f-strings/`.format()` into SQL). `closing()` wraps `conectar()`, never a bare `with conectar() as conn`. Comment `# WR-02:` explaining why (`app/db.py:29-31`) should be referenced, not necessarily re-copied verbatim, if the same rationale applies.

### FastAPI Dependency Pattern
**Source:** `app/main.py:55-70`, attachment at `:132-136`
**Apply to:** `usuario_atual`, `exigir_admin`, and any per-route guard on `/health`, `/`, `/static/*`, `POST /api/briefings`, `GET /api/historico`
Dependency function takes `Request` (or nothing), raises `HTTPException(status_code=..., detail="...")` on failure, is attached via `dependencies=[Depends(fn)]` when no return value is needed by the route body, or `param: T = Depends(fn)` when the route needs the resolved value (new pattern for `usuario_atual`, no exact precedent but directly implied by FastAPI + D-17's own wording).

### Error Handling / Authored-Literal Rule
**Source:** `app/main.py:35-39` (`AVISO_CACHE_INDISPONIVEL`, `MSG_FALHA_GENERICA` module constants) and inline comments at `:107-113`, `:194-196`, `:218-223`; CONVENTIONS.md "Error Handling" section.
**Apply to:** every user-facing message in `auth.py`/new routes (login failure, session expired, 403 message)
**Rule (quote from `app/main.py:35-38`):**
> "L-02/D-05/D-06: literais autorados por nos. Nunca interpolamos str() de uma excecao nao autorada nestes campos — o vendedor le apenas a frase generica, nunca o texto arbitrario de uma falha de terceiro (SQLite, heuristico, etc)."

Concretely: never do `detail=str(exc)` for a raw `sqlite3.Error`/unexpected exception. Login failure detail must be a fixed, generic Portuguese string (avoid username enumeration — CONTEXT.md threat_seeds names this explicitly), e.g. a single constant like `MSG_LOGIN_INVALIDO = "Usuario ou senha invalidos."` used for both "user not found" and "wrong password" cases, mirroring the `AVISO_CACHE_INDISPONIVEL`/`MSG_FALHA_GENERICA` module-constant style.

### Env Var Reading
**Source:** `app/config.py:22-25`
**Apply to:** D-19 admin bootstrap (`ADMIN_USERNAME`, `ADMIN_SENHA` or similar)
Function, not module-level constant, reading `os.getenv(...)` at call time — required so tests can `monkeypatch.setenv`/`delenv` at runtime (see `app/config.py:9-11` docstring rationale, and `test_smoke.py:47-54` for the calling-side test pattern).

### Naming/Language Convention
All new identifiers, docstrings, and comments must be Portuguese, matching every existing file (`db.py`, `main.py`, `config.py`, `schemas.py`, `fetcher.py`, `extractor.py`, `test_smoke.py`, `static/index.html`). Function names snake_case (`gerar_hash_senha`, `verificar_senha`, `criar_sessao`, `validar_sessao`, `usuario_atual`, `exigir_admin`, `semear_admin_inicial`); classes PascalCase (`LoginRequest`, `Usuario`, `LoginResponse`); constants UPPER_SNAKE_CASE Portuguese (`MSG_LOGIN_INVALIDO`, not `INVALID_LOGIN_MSG`). Do not introduce English identifiers even for standard auth terms — the codebase has zero precedent for English naming outside third-party API field names.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `app/auth.py` as a whole module | service | mixed | No prior standalone service module exists (only `db.py`, `fetcher.py`, `extractor.py`, all narrowly scoped); nearest neighbours are `db.py` (persistence half) and `config.py`/`fetcher.py` (pure-function half). Compose from both patterns above rather than inventing a new module convention. |
| First-admin bootstrap script/mechanism (D-19) | config/utility | batch | No `scripts/` directory or CLI-seed precedent anywhere in STRUCTURE.md; nearest neighbour is the `@app.on_event("startup")` hook in `app/main.py:73-75` combined with `config.py`'s env-read style. |
| Guarding a `StaticFiles` mount (`/static/*`) | middleware | request-response | `app.mount(...)` (`app/main.py:249`) has no decorator/`Depends` attachment point in this codebase's usage; planner must decide approach (e.g. wrap with a custom ASGI middleware, or leave public since only CSS/no sensitive assets are served today). |

## Metadata

**Analog search scope:** `app/` (all 5 modules), `static/index.html`, `test_smoke.py`, `.planning/codebase/*.md`, `.planning/phases/06-auth/06-CONTEXT.md`, `SPEC-sales-intel.md` (referenced via CONTEXT.md quotes, not re-read in full — sections 8/10/15 already summarized in CONTEXT.md).
**Files scanned:** 8 source/test files fully read; 4 `.planning/codebase/*.md` reference docs fully read.
**Pattern extraction date:** 2026-08-27
