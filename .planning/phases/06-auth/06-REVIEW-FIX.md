---
phase: 06-auth
fixed_at: 2026-08-27T19:35:58Z
review_path: .planning/phases/06-auth/06-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 6: Code Review Fix Report

**Fixed at:** 2026-08-27T19:35:58Z
**Source review:** .planning/phases/06-auth/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2 (fix_scope = critical_warning; 0 Critical, 2 Warning; Info findings out of scope)
- Fixed: 2
- Skipped: 0

**Verification environment:** All edits, syntax checks, and the `python -m pytest test_smoke.py -q`
run below were performed inside an isolated git worktree
(`.claude/worktrees/rf-06-386-1787859260`, branch `gsd-reviewfix/06-386`), then fast-forwarded
into `main` via the cleanup tail. The 54/54 pass count is reproducible from `main` at the
resulting commits.

## Fixed Issues

### WR-01: Login response timing leaks whether an account is deactivated

**Files modified:** `app/auth.py`
**Commit:** 2aebc3a
**Applied fix:** In `autenticar()`, the deactivated-user branch now runs `verificar_senha(senha,
_HASH_DUMMY)` (the same dummy-hash KDF call used on the nonexistent-user branch) before
returning `None`, closing the ~150x timing gap that let an attacker fingerprint deactivated
accounts by response latency alone. Matches the fix suggested in REVIEW.md exactly; code context
was unchanged from the review.

### WR-02: `usuarios.papel` has no DB-level constraint; an out-of-enum value crashes every route for that user instead of failing cleanly

**Files modified:** `app/db.py`, `app/main.py`
**Commit:** acc947e
**Applied fix:** Added `CHECK (papel IN ('vendedor', 'admin'))` to the `usuarios` table
definition in `db.py` (belt-and-suspenders for fresh databases, per `CREATE TABLE IF NOT
EXISTS`). Additionally applied the review's secondary suggestion: `usuario_atual()` in `main.py`
now catches `pydantic.ValidationError` when constructing `Usuario(**usuario)` and raises a 401
(`MSG_NAO_AUTENTICADO`) instead of letting the exception propagate as an unhandled 500 — a
corrupted/out-of-enum row now degrades to "no valid session" rather than crashing every
authenticated route for that user. `ValidationError` was already imported in `main.py`, no new
import needed.

## Skipped Issues

None — both in-scope findings were fixed.

**Note:** Info-level findings IN-01 through IN-05 were out of scope for this run (`fix_scope:
critical_warning`) and were not addressed. They remain documented in `06-REVIEW.md` for a future
`--fix-scope all` pass or manual follow-up.

## Verification

`python -m pytest test_smoke.py -q` — 54 passed, 0 failed (run after both fixes were applied, in
the isolated worktree, before the fast-forward into `main`). No regressions introduced by either
fix.

---

_Fixed: 2026-08-27T19:35:58Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
