---
phase: 06-auth
reviewed: 2026-08-27T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - .env.example
  - SPEC-sales-intel.md
  - app/auth.py
  - app/config.py
  - app/db.py
  - app/main.py
  - app/schemas.py
  - static/index.html
  - test_smoke.py
findings:
  critical: 0
  warning: 2
  info: 5
  total: 7
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-08-27T00:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Re-reviewed the Phase 6 auth surface from scratch (`app/auth.py`, `app/config.py`, `app/db.py`,
`app/main.py`, `app/schemas.py`, `static/index.html`, `test_smoke.py`, `.env.example`,
`SPEC-sales-intel.md`), verifying every claim against the current source rather than trusting
the prior `06-REVIEW.md` on disk. `python -m pytest test_smoke.py -q` passes 54/54.

The core access-control guarantees hold up under direct probing: route-guard completeness
(D-17, confirmed via the route-inventory test and by hand), the `/api/historico` IDOR guard
(D-18, confirmed with two vendors and an admin), fail-closed `db.listar()`, SQL parameterization
everywhere, `scrypt` + `hmac.compare_digest` password verification, session tokens stored only
as a sha256 digest, session-fixation avoidance (token always reissued on login), and
`escapar()`'s coverage of the single-quote attribute context all check out.

Two Warning-level defects reproduced independently below (both pre-existing from the prior
review pass and still present in the current source), plus five Info-level items — two carried
over (verified still valid), and three new ones found in this pass (IN-01 was previously filed
as a `main.py`-only finding; it is retained here with the pre-existing `db.py` history noted).
None of these break the SPEC §15 done-criterion (a vendedor cannot reach an admin route).

## Warnings

### WR-01: Login response timing leaks whether an account is deactivated

**File:** `app/auth.py:162-184` (`autenticar`), specifically the early return at lines 172-174

**Issue:** `autenticar()` deliberately equalizes timing between "user does not exist" and "wrong
password for an existing user" by running the scrypt KDF against a dummy hash on the
nonexistent-user path:

```python
usuario = buscar_usuario_por_username(username)
if usuario is None:
    verificar_senha(senha, _HASH_DUMMY)   # KDF work happens here
    return None

if not usuario["ativo"]:
    return None                            # <-- returns with NO KDF work at all

if not verificar_senha(senha, usuario["senha_hash"]):
    return None
```

The **deactivated-user** branch returns immediately, before any scrypt call. I reproduced this
directly (median of 5 calls each, same process, same machine):

```
wrong password on active user: 63.6 ms
nonexistent user:               64.7 ms
deactivated user:                0.4 ms
```

A ~150x timing gap between the deactivated-account path and every other outcome — even though
all three return the identical `401 {"detail": "Usuario ou senha invalidos."}` — lets an
attacker who can send login attempts (rate-limited but not blocked: 10/IP and 5/username per 5
minutes) fingerprint which candidate usernames belong to deactivated accounts, purely from
response latency. This directly contradicts the module docstring's stated intent ("nunca um
motivo diferente para cada caso") and the equalization the nonexistent-user branch already goes
out of its way to provide.

**Fix:** Do the same dummy-hash KDF work on the inactive branch before returning:

```python
if not usuario["ativo"]:
    verificar_senha(senha, _HASH_DUMMY)
    return None

if not verificar_senha(senha, usuario["senha_hash"]):
    return None
```

### WR-02: `usuarios.papel` has no DB-level constraint; an out-of-enum value crashes every route for that user instead of failing cleanly

**File:** `app/db.py:48-56` (table definition, no `CHECK`); `app/main.py:153-163` (`usuario_atual`),
`166-173` (`exigir_admin`), `196-224` (`login`), `227-230` (`eu`)

**Issue:** `CREATE TABLE ... usuarios (... papel TEXT NOT NULL ...)` has no `CHECK` constraint,
so nothing at the database layer stops a row from holding a `papel` outside
`{"vendedor", "admin"}`. Every route that turns a DB row into a response does `Usuario(**usuario)`,
and `Usuario.papel` is `Literal["vendedor", "admin"]` (`app/schemas.py:95`). All current write
paths are gated by that same literal or a hardcoded `"admin"`, so this isn't reachable through
the API today — but a manual DB fix during an incident, a future migration, or a bug in a later
phase can write an out-of-enum value, and I reproduced the resulting failure directly:

```python
conn.execute("UPDATE usuarios SET papel = ? WHERE id = ?", ("supervisor", uid)); conn.commit()
client.post("/api/auth/login", json={"username": "raro", "senha": "..."})
# -> pydantic_core._pydantic_core.ValidationError: 1 validation error for Usuario
#    papel: Input should be 'vendedor' or 'admin' [type=literal_error, ...]
```

There is no exception handler registered for `ValidationError` at the route level (`main.py`
only catches it locally inside `_extrair_com_fallback`'s cache-parsing branch, which is
unrelated), so this propagates as an unhandled 500 in production. Every subsequent request for
that account — login, `/api/auth/me`, `/api/briefings`, `/api/historico` — crashes the same way
until the row is manually fixed, effectively locking the account out with a 500 instead of a
controlled error.

**Fix:** Add a `CHECK` constraint (belt-and-suspenders; only affects fresh databases given
`CREATE TABLE IF NOT EXISTS`, same caveat as the rest of the schema):

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

Additionally, `usuario_atual` could catch `ValidationError` when constructing `Usuario(**usuario)`
and translate it into a 401 (treat an unparseable session row like "no valid session"), so a
corrupted row degrades instead of crashing every route for that user.

## Info

### IN-01: `GET /api/historico`'s `limite` query parameter has no bounds

**File:** `app/main.py:452-460`; `app/db.py:146-182`

**Issue:** `limite: int = 50` has no `ge=`/`le=` constraint (this predates Phase 6 — the
unbounded parameter existed in the pre-auth version of the route too, and Phase 6 only added
the session-derived visibility filter around it). SQLite treats a negative `LIMIT` as "no
limit," so `?limite=-1` returns every row the caller is authorized to see instead of the
documented 50-row default. This does not cross an authorization boundary (`db.listar` still
filters by `dono`/`ver_tudo` first), so it's not a security issue, but it silently defeats the
documented default cap.

**Fix:** `limite: int = Query(50, ge=1, le=200)`.

### IN-02: Username is never normalized (trim/case) on either the create-user or login path

**File:** `app/schemas.py:77-87, 99-110`; `app/auth.py:105-129, 162-184`

**Issue:** `LoginRequest.username` and `CriarUsuarioRequest.username` accept any string within
the length bounds; nothing trims whitespace or normalizes case server-side. The front-end trims
(`static/index.html:298`), but that's UI convenience only — a direct API call can create
`"chefe"`, `" chefe"`, and `"Chefe"` as three distinct accounts, since SQLite's default `UNIQUE`
comparison is byte-exact. Not a privilege issue by itself, but a footgun for admins managing
users and an enforcement gap between what the UI assumes and what the API accepts.

**Fix:** Normalize (`.strip()`, and consider case-folding) `username` via a Pydantic validator
on `LoginRequest`/`CriarUsuarioRequest`, or at minimum inside `criar_usuario`/`autenticar`.

### IN-03: `Secure` cookie flag is derived from `request.url.scheme`, which reads `http` behind a typical TLS-terminating reverse proxy

**File:** `app/main.py:219-223`

**Issue:** `secure=request.url.scheme == "https"` is correct for the current target
(`http://localhost`) but will silently produce a non-`Secure` session cookie in a Phase-7-style
production deployment behind a reverse proxy that terminates TLS and forwards over plain HTTP —
Starlette sees `scheme == "http"` there unless the proxy sets `X-Forwarded-Proto` and the ASGI
server is explicitly configured to trust and honor it (e.g. uvicorn `--proxy-headers` plus a
trusted-hosts list). No action needed for Phase 6 itself; flagging so it isn't lost before
packaging/deployment.

**Fix:** When wiring up the production reverse proxy in Phase 7, configure uvicorn's
`--proxy-headers`/`--forwarded-allow-ips` (or equivalent) so `request.url.scheme` reflects the
original client scheme.

### IN-04: No regression test exercises the timing gap described in WR-01

**File:** `test_smoke.py:570-593` (`test_login_invalido_nao_distingue_usuario_inexistente_de_senha_errada`)

**Issue:** The existing test proves the nonexistent-user and wrong-password-on-existing-user
paths return byte-identical JSON bodies and status codes, which is exactly what it's designed
to prove — but nothing in the suite exercises the deactivated-user path against the same
equivalence, nor asserts anything about response latency. As a result, the regression this
review demonstrates in WR-01 would not have been caught by CI; a future refactor that
reintroduces or worsens the same class of timing gap would also slip through silently.

**Fix:** Add a case (or extend the existing test) covering a deactivated user with a wrong
password, asserting identical status/body to the other two cases. A true timing assertion is
harder to make non-flaky in CI, but even a coarse assertion (e.g. patch `verificar_senha` with a
`Mock` and assert it was called exactly once on all three branches) would catch a regression
like the one in WR-01 without relying on wall-clock measurement.

### IN-05: In-memory rate-limit dictionaries grow without bound, keyed partly by attacker-controlled input

**File:** `app/main.py:63-65` (`_requisicoes_por_ip`), `99-104`
(`_tentativas_login_por_ip`, `_falhas_login_por_usuario`)

**Issue:** All three sliding-window limiters prune stale *timestamps* from each list
(`historico[:] = [t for t in historico if t >= limite_inferior]`), but never remove the *key*
itself once its list becomes empty. `_falhas_login_por_usuario` in particular is keyed by the
raw `username` string submitted to the public, unauthenticated `POST /api/auth/login` endpoint
(bounded only to 64 characters by `LoginRequest.username`, but unbounded in count) — every
distinct username ever attempted, real or fabricated, leaves a permanent entry in the dict for
the life of the process. This is adjacent to the "memory leak" category called out of scope for
this review, but it differs in that the growth is directly driven by unauthenticated,
attacker-controlled request content rather than internal algorithmic behavior, so it is worth
recording as a robustness gap even though it isn't classified as a blocking issue here.

**Fix:** After pruning, delete the key when its list is empty, e.g.:

```python
falhas[:] = [t for t in falhas if t >= limite_inferior]
if not falhas:
    del _falhas_login_por_usuario[username]
```

(guarded appropriately for the case where the key is being freshly inserted vs. pruned to empty
in the same call) — apply the same pattern to the other two dictionaries.

---

_Reviewed: 2026-08-27T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
