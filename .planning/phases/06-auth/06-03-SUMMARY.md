---
phase: 06-auth
plan: 03
subsystem: auth
tags: [sqlite, fastapi-depends, idor, ownership, read-time-filtering]

# Dependency graph
requires:
  - phase: 06-auth (plano 06-01)
    provides: "app/auth.py completo, dependencias usuario_atual/exigir_admin, helper de teste _cliente_autenticado"
  - phase: 06-auth (plano 06-02)
    provides: "SPEC-sales-intel.md S8/S10 documentando briefings.owner e o inventario de rotas com guarda"
provides:
  - "app/db.py: coluna briefings.owner adicionada de forma idempotente e aditiva; salvar(dono=) preserva o dono na recoleta; listar(dono=, ver_tudo=) com ramo fail-closed"
  - "app/main.py: POST /api/briefings e GET /api/historico exigem usuario_atual; historico ramifica por papel (admin ve tudo, vendedor ve so o proprio)"
  - "oito testes novos e cinco testes existentes migrados para _cliente_autenticado"
affects: [06-04, 06-05]

# Actuals (#2632)
actuals:
  tokens: 5059
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Filtro de visibilidade vive na leitura (db.listar), nunca na escrita nem em migracao — mesmo molde de D-09/D-10 em db.buscar()"
    - "Fail-closed por omissao: db.listar sem dono e sem ver_tudo devolve lista vazia, nunca a tabela inteira"
    - "Clausula ON CONFLICT que atualiza conteudo mas exclui a coluna de procedencia (owner), preservando o primeiro coletor"

key-files:
  created: []
  modified:
    - app/db.py
    - app/main.py
    - test_smoke.py

key-decisions:
  - "Checkpoint do plano (D-18: politica de dono da linha de briefing) resolvido pelo usuario com a opcao a: coluna owner em briefings, primeiro coletor fica com a linha. Opcao b (tabela separada de acesso por usuario) rejeitada explicitamente."
  - "Trade-off aceito e documentado, nao tratado como defeito: se o vendedor B recoleta uma URL ja coletada pelo vendedor A, o briefing atualiza normalmente na resposta, mas a linha permanece no historico de A e nao aparece no de B."
  - "Linha de briefings anterior a Fase 6 (dono nulo) e visivel apenas para admin — decisao ja travada no CONTEXT e agora travada por teste (test_linha_sem_dono_so_aparece_para_admin)."
  - "Sem migracao de backfill: nenhuma linha existente de briefings foi tocada, removida ou reescrita pela adicao da coluna (D-18, herdado de T-05-36)."

patterns-established:
  - "Coluna nova em tabela existente via PRAGMA table_info + ALTER TABLE guardado, dentro do mesmo criar_tabelas() idempotente — padrao reutilizavel para qualquer coluna aditiva futura em SQLite deste projeto"

requirements-completed: [L-07, L-09, D-17, D-18, SPEC-8, SPEC-10, SPEC-15]

coverage:
  - id: D1
    description: "POST /api/briefings e GET /api/historico exigem sessao — 401 sem cookie (fecha R-01 nas duas rotas de dado)"
    requirement: "L-07"
    verification:
      - kind: e2e
        ref: "test_smoke.py#test_briefings_sem_cookie_devolve_401"
        status: pass
      - kind: e2e
        ref: "test_smoke.py#test_historico_sem_cookie_devolve_401"
        status: pass
    human_judgment: false
  - id: D2
    description: "Vendedor ve no historico apenas as linhas que ele proprio gerou"
    requirement: "D-18"
    verification:
      - kind: e2e
        ref: "test_smoke.py#test_vendedor_ve_apenas_o_proprio_historico"
        status: pass
    human_judgment: false
  - id: D3
    description: "Linha de briefing sem dono (pre-Fase 6) e visivel apenas para admin, nunca para vendedor"
    requirement: "D-18"
    verification:
      - kind: e2e
        ref: "test_smoke.py#test_linha_sem_dono_so_aparece_para_admin"
        status: pass
    human_judgment: false
  - id: D4
    description: "criar_tabelas() e repetivel e nao toca em linha ja gravada; coluna owner nasce nula"
    requirement: "D-18"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_criar_tabelas_e_repetivel_e_preserva_linhas_antigas"
        status: pass
    human_judgment: false
  - id: D5
    description: "db.listar sem dono e sem ver_tudo e fail-closed (lista vazia, nunca a tabela inteira)"
    requirement: "D-18"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_listar_sem_dono_e_sem_ver_tudo_devolve_lista_vazia"
        status: pass
    human_judgment: false
  - id: D6
    description: "listar por dono nunca devolve linha de outro dono nem linha sem dono"
    requirement: "D-18"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_listar_por_dono_nao_devolve_linha_de_outro_dono_nem_linha_sem_dono"
        status: pass
    human_judgment: false
  - id: D7
    description: "Recoleta da mesma URL por outro dono atualiza o conteudo mas nao transfere o dono"
    requirement: "D-18"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_recoleta_da_mesma_url_por_outro_dono_nao_troca_o_dono"
        status: pass
    human_judgment: false
  - id: D8
    description: "Cinco testes preexistentes de POST /api/briefings continuam passando com a guarda nova, sem nenhuma assercao afrouxada"
    requirement: "L-07"
    verification:
      - kind: unit
        ref: "python -m pytest -q — 32 passed"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-27
status: complete
---

# Phase 6 Plan 3: Guardas nas rotas de dado e dono do historico Summary

**POST /api/briefings e GET /api/historico exigem sessao, e o historico passa a mostrar ao vendedor apenas o que ele proprio gerou — coluna owner aditiva em briefings, filtro vivendo na leitura (D-18), sem tocar em nenhuma linha existente.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-08-27T18:00:00Z (aprox.)
- **Completed:** 2026-08-27T18:21:22Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `app/db.py::criar_tabelas()` ganha coluna `briefings.owner` (TEXT, nulavel), adicionada de forma idempotente via `PRAGMA table_info` + `ALTER TABLE` guardado — chamada repetida nao levanta e nenhuma linha existente e tocada.
- `app/db.py::salvar` grava o dono a partir do parametro `dono`; a clausula `ON CONFLICT` atualiza conteudo mas nunca transfere a procedencia — o primeiro coletor fica com a linha.
- `app/db.py::listar` ganha `dono` e `ver_tudo`: visao total do admin, filtro por dono com junção a esquerda em `usuarios`, e um terceiro ramo deliberadamente fail-closed (lista vazia) quando nenhum dos dois e informado.
- `POST /api/briefings` exige `usuario_atual` alem do rate limit por IP ja existente (os dois controles somam); grava o dono do briefing a partir da sessao, nunca de um campo da requisicao.
- `GET /api/historico` exige `usuario_atual` e ramifica por papel — sem nenhum parametro de dono vindo do cliente, fechando IDOR por desenho.
- Cinco testes preexistentes de `POST /api/briefings` migrados para `_cliente_autenticado`, sem nenhuma assercao removida ou afrouxada.
- Oito testes novos: quatro cobrindo a coluna/leitura de `app/db.py` e quatro cobrindo as guardas e a ramificacao por dono em `app/main.py`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Coluna de dono e leitura filtrada, sem tocar em linha existente (D-18, L-09)** - `a03a858` (feat)
2. **Task 2: Guardas em POST /api/briefings e GET /api/historico, e os testes existentes acompanhando (L-07, D-17, D-18)** - `9dd4355` (feat)

_Nota: as tasks deste plano sao `tdd="true"` mas do tipo `auto` (nao TDD RED/GREEN/REFACTOR classico) — cada uma segue o protocolo de commit atomico unico ja usado no plano 06-01: implementacao real + `<verify>` real num commit so, comportamento documentado para tasks `type="auto"` com testes escritos junto da implementacao._

## Files Created/Modified

- `app/db.py` - Coluna `briefings.owner` idempotente; `salvar(url, briefing, extrator, dono=None)`; `listar(limite=50, dono=None, ver_tudo=False)` com junção a esquerda em `usuarios` e ramo fail-closed
- `app/main.py` - `gerar_briefings` com `Depends(usuario_atual)` gravando o dono; `historico(limite, usuario)` ramificando por papel
- `test_smoke.py` - Quatro testes de banco (Task 1), quatro testes de rota (Task 2), cinco testes preexistentes migrados para `_cliente_autenticado`

## Decisions Made

**Checkpoint resolvido pelo usuario (decisao registrada acima, D-18):** a pergunta em aberto sobre como gravar o dono da linha de briefing — dado que `briefings.url` e chave primaria e a tabela e um cache compartilhado com uma unica linha por URL — foi respondida com a opcao `a`: coluna `owner` em `briefings`, primeiro coletor fica com a linha. A opcao `b` (tabela separada de acesso por usuario) foi rejeitada explicitamente pelo usuario por divergir do texto literal de D-18.

**Trade-off aceito, nao um defeito:** se o vendedor B recoleta uma URL ja coletada pelo vendedor A, o briefing atualiza normalmente na resposta que B recebe, mas a linha em `briefings` continua no historico de A e nao aparece no de B (a clausula `ON CONFLICT` de `salvar` nao transfere `owner`). O usuario confirmou explicitamente este comportamento ao aprovar a opcao `a`.

**Sem migracao de backfill:** nenhuma linha existente de `briefings` foi removida, reescrita ou teve seu dono atribuido retroativamente — herdado de D-18/T-05-36. Linha anterior a Fase 6 fica com dono nulo, visivel apenas para admin.

## Deviations from Plan

None - plan executed exactly as written, apos a resolucao do checkpoint pelo humano (opcao `a`).

O `<verify>` inline do Task 2 no PLAN.md usa `getattr(r, 'methods', None)` para filtrar rotas antes de acessar `r.dependant` — nesta versao do FastAPI, as rotas de documentacao (`/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect`) sao `starlette.routing.Route` puras (tem `.methods` mas nao `.dependant`), o que faz o script literal do plano levantar `AttributeError`. Nao e um defeito no codigo do plano: usei `hasattr(r, 'dependant')` como filtro (que so aceita `APIRoute`) para rodar a mesma verificacao, e ela passou. As asserções de negocio (guarda de `usuario_atual` em `/api/historico` e `/api/briefings`, `_checar_rate_limit` preservado) sao as mesmas do script original.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Nenhum pacote novo foi instalado (`git diff --name-only requirements.txt` vazio, confirmado apos as duas tasks).

## Next Phase Readiness

- As duas rotas que carregam dado de verdade exigem sessao, e o historico mostra a cada um exatamente o que lhe pertence — a segunda metade do fechamento do aceite R-01 esta completa nestas duas rotas (o inventario formal de **todas** as rotas, travado por teste, fica para o plano 06-04, conforme ja previsto no threat model deste plano).
- `db.listar(dono=, ver_tudo=)` e `db.salvar(dono=)` estao prontos para qualquer consumidor futuro que precise do mesmo recorte de visibilidade.
- Plano 06-04 (cadastro/desativacao de usuario, inventario formal de rotas) e Plano 06-05 (UI de login/historico/admin) podem prosseguir sem ajuste retroativo neste plano.
- Sem bloqueios.

---
*Phase: 06-auth*
*Completed: 2026-08-27*

## Self-Check: PASSED

- FOUND: `app/db.py`
- FOUND: `app/main.py`
- FOUND: `test_smoke.py`
- FOUND: `.planning/phases/06-auth/06-03-SUMMARY.md`
- FOUND commit: `a03a858`
- FOUND commit: `9dd4355`
