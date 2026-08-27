---
phase: 06-auth
plan: 02
subsystem: docs
tags: [spec, scrypt, sessions, authorization, threat-model]

# Dependency graph
requires:
  - phase: 06-auth (plano 06-01)
    provides: "app/auth.py (scrypt, sessao opaca), tabelas usuarios e sessoes em app/db.py, rotas de login/me/admin/logout em app/main.py — o codigo real que este plano documenta"
provides:
  - "SPEC-sales-intel.md S8: tabela usuarios com senha_hash em scrypt, tabela sessoes nova, coluna briefings.owner com politica de leitura D-18, conteudo_hash marcado nao implementado"
  - "SPEC-sales-intel.md S10: inventario de onze rotas com guarda, nota 401/403, renovacao de R-08 e R-11"
  - "SPEC-sales-intel.md S13: ADMIN_USERNAME e ADMIN_SENHA sem valor (D-19)"
affects: [06-03, 06-04, 06-05]

# Actuals (#2632)
actuals:
  tokens: 1411
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SPEC como contrato escrito antes do teste de inventario de rotas (plano 06-04) — S10 vira a lista que o teste trava em codigo"

key-files:
  created: []
  modified:
    - SPEC-sales-intel.md

key-decisions:
  - "D-15 aplicada na SPEC: senha_hash documentado como scrypt$n$r$p$salt$chave, com paragrafo de divergencia registrada citando argon2 (versao anterior) e L-06 (motivo) — argon2 permanece no documento de proposito, so dentro desse paragrafo"
  - "D-16 aplicada na SPEC: tabela sessoes nova (token_hash, usuario_id, criada_em, expira_em), token opaco de 32 bytes, revogacao por remocao de linha, duracao de 12h"
  - "D-18 aplicada na SPEC: coluna briefings.owner nula para linhas anteriores a Fase 6; politica de leitura documentada (vendedor ve as proprias, admin ve todas, linha sem dono visivel so para admin), sem migracao destrutiva"
  - "D-19 aplicada na SPEC: ADMIN_USERNAME e ADMIN_SENHA em S13 sem nenhum valor de exemplo"
  - "S10 documenta duas rotas de admin (POST /api/admin/usuarios, POST /api/admin/usuarios/{usuario_id}/ativo) que ainda nao existem em app/main.py — intencional: o plano escreve o contrato antes da implementacao (planner_notes do 06-02-PLAN.md), para o plano 06-04 travar o mesmo inventario em teste"

patterns-established:
  - "Divergencia entre SPEC e codigo e nomeada num paragrafo proprio, nunca apagada silenciosamente (D-15)"

requirements-completed: [D-15, D-16, D-18, D-19, L-08, SPEC-8, SPEC-10, SPEC-13]

coverage:
  - id: D1
    description: "SPEC S8 descreve senha_hash como scrypt (formato scrypt$n$r$p$salt$chave), com a divergencia de argon2 registrada e nao apagada"
    requirement: "D-15"
    verification:
      - kind: other
        ref: "python -c script inline (06-02-PLAN.md Task 1 <verify>) checando presenca de 'argon2', 'scrypt', D-15 no documento"
        status: pass
    human_judgment: false
  - id: D2
    description: "SPEC S8 ganha tabela sessoes (token_hash, usuario_id, criada_em, expira_em) documentando D-16"
    requirement: "D-16"
    verification:
      - kind: other
        ref: "python -c script inline (06-02-PLAN.md Task 1 <verify>) checando 'sessoes' e 'token_hash'"
        status: pass
    human_judgment: false
  - id: D3
    description: "SPEC S8 ganha coluna briefings.owner e nota de politica de leitura (D-18), e marca conteudo_hash como nao implementado (R-10)"
    requirement: "D-18"
    verification:
      - kind: other
        ref: "python -c script inline (06-02-PLAN.md Task 1 <verify>) checando 'owner', 'conteudo_hash', 'R-10'"
        status: pass
    human_judgment: false
  - id: D4
    description: "SPEC S13 ganha ADMIN_USERNAME= e ADMIN_SENHA= sem nenhum valor de exemplo (D-19)"
    requirement: "D-19"
    verification:
      - kind: other
        ref: "python -c script inline (06-02-PLAN.md Task 1 <verify>) checando ocorrencia unica de cada variavel seguida de quebra de linha"
        status: pass
    human_judgment: false
  - id: D5
    description: "SPEC S10 vira inventario de onze rotas com guarda declarada, nota 401/403, e renovacao explicita de R-08/R-11"
    requirement: "D-17"
    verification:
      - kind: other
        ref: "python -c script inline (06-02-PLAN.md Task 2 <verify>) checando as onze rotas, usuario_atual, exigir_admin, RF13, R-08, R-11, D-17, L-07, 401, 403"
        status: pass
    human_judgment: false
  - id: D6
    description: "Nenhum arquivo de codigo foi tocado; pytest continua verde apos as duas tasks"
    verification:
      - kind: unit
        ref: "python -m pytest -q — 24 passed"
        status: pass
    human_judgment: false

duration: 2min
completed: 2026-08-27
status: complete
---

# Phase 6 Plan 2: SPEC reflete auth e autorizacao do codigo real Summary

**SPEC-sales-intel.md S8/S10/S13 atualizadas para descrever o que o plano 06-01 realmente construiu — scrypt em vez de argon2 (divergencia nomeada, nao apagada), tabela sessoes, coluna briefings.owner, e um inventario de onze rotas com a guarda de cada uma.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-08-27T18:08:40Z
- **Completed:** 2026-08-27T18:10:02Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- S8: tabela `usuarios` documenta `senha_hash` no formato autodescritivo `scrypt$n$r$p$salt$chave`, com paragrafo de divergencia registrada citando D-15 e L-06 — a palavra `argon2` permanece no documento, mas so dentro desse paragrafo.
- S8: tabela `sessoes` nova (`token_hash`, `usuario_id`, `criada_em`, `expira_em`), documentando D-16 (token opaco, digest sha256, revogacao por `DELETE`, 12h de duracao).
- S8: coluna `briefings.owner` documentada com a politica de leitura de D-18 (vendedor ve as proprias linhas, admin ve todas, linha sem dono visivel so para admin, sem migracao destrutiva).
- S8: `conteudo_hash` marcado como especificado e nao implementado, referenciando o risco aceito R-10 da Fase 5.
- S13: `ADMIN_USERNAME=` e `ADMIN_SENHA=` acrescentadas sem nenhum valor de exemplo, documentando D-19.
- S10: a linha solta "Rotas do bonus 2" virou uma tabela de onze rotas com guarda declarada, mais notas sobre 401 vs 403, `/health` publico (R-08 renovado) e configuracao fora da interface (R-11 renovado).

## Task Commits

Each task was committed atomically:

1. **Task 1: SPEC S8 e S13 refletem scrypt, as tabelas novas e as variaveis do bootstrap** - `df505bb` (docs)
2. **Task 2: SPEC S10 vira inventario de rotas com a guarda de cada uma** - `6945a58` (docs)

## Files Created/Modified

- `SPEC-sales-intel.md` - S8 (tabelas `usuarios`, `sessoes`, coluna `briefings.owner`), S10 (inventario de rotas), S13 (variaveis de bootstrap de admin)

## Decisions Made

- D-15, D-16, D-18, D-19 aplicadas exatamente como travadas em `06-CONTEXT.md` — ver `key-decisions` no frontmatter.
- S10 documenta duas rotas de admin (`POST /api/admin/usuarios`, `POST /api/admin/usuarios/{usuario_id}/ativo`) que ainda **nao existem** em `app/main.py` hoje — isso e intencional e nao e divergencia: o `planner_notes` do `06-02-PLAN.md` diz explicitamente que este plano escreve o contrato **antes** do codigo, para que o teste de inventario de rotas do plano 06-04 tenha algo a conferir contra o codigo real quando essas rotas forem implementadas.
- Removi a qualificacao "(so se o bonus 2 entrar)" do titulo da tabela `usuarios`, porque o bonus 2 esta em implementacao nesta fase — mantido dentro do escopo de S8, sem reescrever a secao.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Nenhum arquivo de codigo foi tocado (`git diff --stat` confirma apenas `SPEC-sales-intel.md` nos dois commits deste plano).

## Next Phase Readiness

- `SPEC-sales-intel.md` S8/S10/S13 agora descrevem o modelo de dados e o contrato de rotas que a Fase 6 realmente constroi, incluindo as duas rotas de admin que os planos 06-04 ainda vai implementar.
- Plano 06-03 pode aplicar `usuario_atual`/`exigir_admin` as rotas existentes (`/health`, `/`, `/static/*`, `POST /api/briefings`, `GET /api/historico`) usando S10 como referencia do que cada rota deve exigir.
- Plano 06-04 pode travar o teste de inventario de rotas (`GUARDAS_ESPERADAS`) diretamente contra a tabela de S10 — as onze linhas ja estao escritas e nomeadas com os mesmos identificadores (`usuario_atual`, `exigir_admin`) usados em `app/main.py`.
- Sem bloqueios.

---
*Phase: 06-auth*
*Completed: 2026-08-27*

## Self-Check: PASSED

- FOUND: `SPEC-sales-intel.md`
- FOUND: `.planning/phases/06-auth/06-02-SUMMARY.md`
- FOUND commit: `df505bb`
- FOUND commit: `6945a58`
- FOUND commit: `5bc14d4`
