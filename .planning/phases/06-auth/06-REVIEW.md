---
phase: 06-auth
reviewed: 2026-08-27T18:52:13Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - app/auth.py
  - app/config.py
  - app/db.py
  - app/main.py
  - app/schemas.py
  - static/index.html
  - test_smoke.py
  - .env.example
  - SPEC-sales-intel.md
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-08-27T18:52:13Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed the Phase 6 auth diff (`be7c78c..HEAD`): `app/auth.py` (new), `app/config.py`,
`app/db.py`, `app/main.py`, `app/schemas.py`, `static/index.html`, `test_smoke.py`,
`.env.example`, and the corresponding `SPEC-sales-intel.md` sections. `python -m pytest
test_smoke.py -q` passes 54/54.

This is a well-built auth phase. The things the phase's own threat model called out —
route-guard completeness (D-17), IDOR on `/api/historico` (D-18), fail-closed `db.listar()`,
password-comparison timing (`hmac.compare_digest` + dummy-hash equalization for
nonexistent users), session-fixation avoidance, SQL parameterization, `escapar()` coverage
of the single-quote attribute context, no secrets in `.env.example` or source — all hold up
under direct testing, including probing past the browser UI straight at the API. The
`/static/*` mount contains only `index.html`, so the documented "no `.dependant`, no
route-inventory coverage" gap is not exploitable in practice.

Two real defects were found and demonstrated by exploit script, both in
`app/auth.py`. Neither breaks the SPEC §15 done-criterion (vendedor cannot reach an admin
route), but both undermine specific security guarantees the code's own comments claim to
provide. Three additional Info-level robustness/quality items are listed below.

## Warnings

### WR-01: Login response timing leaks whether an account is deactivated

**File:** `app/auth.py:162-184` (`autenticar`), short-circuit at line 173-174

**Issue:** `autenticar()` equalizes response timing between "user does not exist" and
"user exists, wrong password" by running the scrypt KDF against a dummy hash on the
nonexistent-user path (`_HASH_DUMMY`, lines 98-102, 168-171) — this part works as designed
and is explicitly tested (`test_login_invalido_nao_distingue_usuario_inexistente_de_senha_errada`).
However, the **inactive-user** path returns `None` immediately, *before* any call to
`verificar_senha`:

```python
usuario = buscar_usuario_por_username(username)
if usuario is None:
    verificar_senha(senha, _HASH_DUMMY)   # KDF work happens here
    return None

if not usuario["ativo"]:
    return None                            # <-- no KDF work at all
```

scrypt with the phase's locked parameters (`n=2**14, r=8, p=1`) takes tens of
milliseconds. Skipping it on the inactive-user branch creates an observable, near-zero-cost
response versus the ~70-100ms taken by every other outcome (wrong password on an active
account, or a nonexistent username) — both of which return the *same* 401 body
(`MSG_LOGIN_INVALIDO`). An attacker who can send login attempts (rate-limited, but not
blocked entirely — 10/IP per 5 min, 5/username per 5 min) can therefore distinguish
"this username belongs to a deactivated account" from "wrong password" / "no such user"
purely by response latency, even though the HTTP status and body are identical in all three
cases. This directly contradicts the stated intent in the module docstring
("nunca um motivo diferente para cada caso") and in the phase's own threat list
(`06-CONTEXT.md` threat_seeds: "timing attack na comparação de hash").

**Concrete failure scenario (measured, via `TestClient`, median of 8 requests each):**
- Active user, wrong password → 401, ~98ms
- Nonexistent user → 401, ~81ms
- Deactivated user, wrong password → 401, **~5ms**

An attacker probing a list of candidate usernames (e.g. former employees) can identify
which ones were deactivated by an admin, purely from timing — information the login
response is explicitly designed not to leak.

**Fix:** Run the same dummy-hash KDF work on the inactive-user branch before returning,
so all three outcomes cost the same:

```python
if not usuario["ativo"]:
    verificar_senha(senha, _HASH_DUMMY)
    return None

if not verificar_senha(senha, usuario["senha_hash"]):
    return None
```

(Verifying against the real stored hash instead of the dummy would also equalize timing,
but would additionally accept-or-reject based on the real password, which is unnecessary
complexity for a branch that must return `None` regardless — the dummy-hash call is
sufficient and matches the existing pattern.)

### WR-02: `usuarios.papel` has no DB-level constraint; an invalid value crashes auth instead of failing cleanly

**File:** `app/db.py:48-56` (table definition); `app/main.py:153-173, 224, 228-230`
(`usuario_atual`, `exigir_admin`, `login`, `eu`)

**Issue:** The `usuarios` table declares `papel TEXT NOT NULL` with no `CHECK` constraint,
so nothing at the database layer prevents a row from holding a value outside
`{"vendedor", "admin"}`. Every route that turns a DB row into a response does
`Usuario(**usuario)`, and `Usuario.papel` is typed `Literal["vendedor", "admin"]`
(`app/schemas.py:95`). Today every *write* path is gated by that same Pydantic literal
(`CriarUsuarioRequest.papel`, or the hardcoded `"admin"` in `semear_admin_inicial`), so the
gap is not reachable through the current API surface — but it is reachable by anything that
writes to the table outside that surface (a future migration, a manual DB fix during an
incident, a bug in a later phase), and when it happens the failure mode is an **unhandled
`pydantic.ValidationError`** inside the auth dependency chain, not a clean 401/403.

**Concrete failure scenario (demonstrated):** with a row whose `papel` was set to
`"supervisor"` directly in the database (no `CHECK` constraint stops this), the very next
`POST /api/auth/login` for that user raises inside `Usuario(**usuario)` in the route body:

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Usuario
papel
  Input should be 'vendedor' or 'admin' [type=literal_error, input_value='supervisor', ...]
```

This propagates as an unhandled exception (a 500 in production, since there is no
exception handler registered for `ValidationError` at the route level — `main.py` only
catches `ValidationError` locally inside `_extrair_com_fallback`'s cache-parsing branch,
which is unrelated). Every subsequent request from that account — including calls to
`usuario_atual`/`exigir_admin` on *every other route* — will crash the same way until the
row is fixed, effectively locking that account out with a 500 instead of a controlled
error.

**Fix:** Add a `CHECK` constraint at the schema level (cheap, no new dependency, consistent
with the "role enum closes at the type" intent already expressed in
`CriarUsuarioRequest`):

```python
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS usuarios (
        id         TEXT PRIMARY KEY,
        username   TEXT NOT NULL UNIQUE,
        senha_hash TEXT NOT NULL,
        papel      TEXT NOT NULL CHECK (papel IN ('vendedor', 'admin')),
        ativo      INTEGER NOT NULL DEFAULT 1,
        criado_em  TEXT NOT NULL
    )
    """
)
```

(Note: since the table already exists via `CREATE TABLE IF NOT EXISTS`, this constraint
only takes effect on fresh databases — same caveat that already applies to the rest of the
schema. Belt-and-suspenders defense in depth, not a replacement.) Additionally, `usuario_atual`
could catch `ValidationError`/`pydantic.ValidationError` when constructing `Usuario(**usuario)`
and translate it into a 401 (treat an unparseable session row the same as "no valid session"),
so a corrupted row degrades instead of crashing every route for that user.

## Info

### IN-01: `GET /api/historico`'s `limite` query parameter has no bounds, silently defeating the documented default cap

**File:** `app/main.py:452-460`

**Issue:** `limite: int = 50` has no `ge=`/`le=` constraint. SQLite interprets a negative
`LIMIT` as "no limit," so `?limite=-1` returns every row the caller is authorized to see
instead of the documented 50-row default. Demonstrated: with 60 owned rows, the
no-parameter call correctly caps at 50, but `?limite=-1` returns all 60. This does not
cross an authorization boundary (`db.listar` still filters by `dono`/`ver_tudo` first), so
it is not a security issue, but it is a documented-behavior/robustness gap — a caller can
silently uncap the query, which is presumably not the intent of picking a default at all.

**Fix:** Constrain the parameter: `limite: int = Query(50, ge=1, le=200)`.

### IN-02: Username is never normalized (trim/case) on either the create-user or login path

**File:** `app/schemas.py:77-87, 99-110`; `app/auth.py:105-129, 162-184`

**Issue:** `LoginRequest.username` and `CriarUsuarioRequest.username` accept any string
within the length bounds; nothing trims whitespace or normalizes case server-side. The
front-end trims (`campoLoginUsuario.value.trim()`, `static/index.html:298`), but that is a
UI convenience only — a direct API call can create `"chefe"` and `" chefe"` (or `"Chefe"`)
as two distinct, fully valid accounts, since SQLite's default `UNIQUE` comparison is
byte-exact. This is not exploitable as a privilege issue on its own, but it is a footgun
for admins managing users (visually indistinguishable duplicate accounts) and an
inconsistency between what the UI enforces and what the API accepts.

**Fix:** Normalize (e.g. `.strip()`) `username` in `CriarUsuarioRequest`/`LoginRequest` via
a Pydantic validator, or at minimum in `criar_usuario`/`autenticar`, so the constraint that
the UI already assumes is actually enforced server-side.

### IN-03: `Secure` cookie flag is derived from `request.url.scheme`, which reads `http` behind a typical TLS-terminating reverse proxy

**File:** `app/main.py:219-223`

**Issue:** `secure=request.url.scheme == "https"` is correct for the current deployment
target (`http://localhost`, per D-16's own stated rationale) and is not a defect for this
phase's scope. It is worth flagging forward, though: behind a reverse proxy that terminates
TLS and forwards over plain HTTP (a common Phase-7/production topology), Starlette sees
`scheme == "http"` unless the proxy sets `X-Forwarded-Proto` *and* the ASGI server is
configured to trust and honor forwarded headers (e.g. uvicorn `--proxy-headers` with a
trusted-hosts list). Without that configuration, the session cookie would silently never
get the `Secure` flag even in a production HTTPS deployment. No action needed for Phase 6;
flagging so it isn't lost before Phase 7 packaging/deployment work.

---

_Reviewed: 2026-08-27T18:52:13Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
