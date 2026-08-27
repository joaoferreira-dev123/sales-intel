---
phase: 06-auth
plan: 05
subsystem: ui
tags: [vanilla-js, xss-escaping, session-cookie, admin-ui, no-build]

# Dependency graph
requires:
  - phase: 06-auth (plano 06-01)
    provides: "rotas POST /api/auth/login, GET /api/auth/me, POST /api/auth/logout; sessao opaca por cookie HttpOnly"
  - phase: 06-auth (plano 06-03)
    provides: "GET /api/historico com recorte de visibilidade por papel, decidido no servidor (D-18)"
  - phase: 06-auth (plano 06-04)
    provides: "POST /api/admin/usuarios, POST /api/admin/usuarios/{usuario_id}/ativo, GET /api/admin/usuarios, todas sob exigir_admin; inventario de rotas travado por teste (D-17)"
provides:
  - "static/index.html: tela de login, estado autenticado, painel de historico e area de administracao, tudo em JavaScript puro inline (L-10)"
  - "static/index.html: escapar() estendido para cobrir aspa simples, fechando o unico ponto de interpolacao em atributo do arquivo (T-06-46)"
  - "test_smoke.py: nove testes novos fechando a fase, incluindo o teste de fechamento do criterio de pronto da SPEC S15"
affects: []

# Actuals (#2632)
actuals:
  tokens: 4531
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Duas tags <main> na mesma pagina, uma por estado (login/app), alternadas via atributo hidden a partir da resposta de GET /api/auth/me — nunca uma decisao de autorizacao, so de apresentacao (L-07)"
    - "Delegacao de clique a partir do contenedor (listaUsuarios.addEventListener) em vez de manipulador embutido na marcacao, para qualquer lista renderizada por template literal com acao por item"
    - "Helper de escape unico (escapar()) reutilizado em toda interpolacao no DOM, inclusive em contexto de atributo (atributo com aspas duplas + entidade numerica para aspa simples)"

key-files:
  created: []
  modified:
    - static/index.html
    - test_smoke.py

key-decisions:
  - "escapar() estendido (nao substituido) para cobrir cinco caracteres, mantendo as oito chamadas existentes intactas — a aspa simples so importa porque a area de admin passa a interpolar o id do usuario num atributo de dado."
  - "Duas <main> na mesma pagina (login/app), cada uma controlada por hidden, em vez de uma unica arvore de DOM com blocos condicionais manipulados via innerHTML — mais simples de auditar visualmente sem framework (L-10), e o HTML5 permite multiplas main desde que no maximo uma fique visivel por vez."
  - "carregarSessao() e a unica fonte de verdade sobre o que a tela desenha: chamada no carregamento da pagina, apos login, apos logout, e reaproveitada quando o historico recebe 401 no meio do uso (sessao expirada)."
  - "Painel de historico e area de admin carregados dentro do caminho de sucesso de carregarSessao(), nao em listeners separados — evita corrida entre 'sessao confirmada' e 'dados carregados'."
  - "O clique de ativar/desativar usuario usa delegacao de evento a partir do contenedor da lista, nunca atributo onclick na marcacao gerada — fecha T-06-48 sem precisar de nenhum framework."

patterns-established:
  - "Interpolacao em atributo HTML: sempre aspas duplas na marcacao, mais escapar() no valor — as duas defesas juntas, nunca uma sozinha (comentario correspondente no codigo)."

requirements-completed: [L-07, L-08, L-10, L-11, D-16, D-17, D-18, SPEC-10, SPEC-15]

coverage:
  - id: D1
    description: "Quem abre a pagina sem sessao ve a tela de login (id=login), com campo de senha mascarado; GET / continua publico"
    requirement: "L-10"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_pagina_inicial_traz_tela_de_login"
        status: pass
    human_judgment: false
  - id: D2
    description: "escapar() passa a cobrir aspa simples (cinco caracteres na classe da expressao regular), fechando o contexto de atributo usado pela area de admin"
    requirement: "SPEC-15"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_escapar_do_front_cobre_aspas_simples"
        status: pass
    human_judgment: false
  - id: D3
    description: "Nenhuma chamada fetch desliga o envio de credencial (cookie HttpOnly da sessao continua sendo enviado)"
    requirement: "D-16"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_front_nao_desliga_o_envio_de_cookie"
        status: pass
    human_judgment: false
  - id: D4
    description: "O script consome as tres rotas de sessao: login, me, logout"
    requirement: "D-16"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_front_consome_as_rotas_de_sessao"
        status: pass
    human_judgment: false
  - id: D5
    description: "Painel de historico consome GET /api/historico, com recorte de visibilidade decidido pelo servidor (nunca por parametro da tela)"
    requirement: "D-18"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_front_consome_a_rota_de_historico"
        status: pass
      - kind: e2e
        ref: "test_smoke.py#test_vendedor_logado_recebe_apenas_o_proprio_historico_pela_api"
        status: pass
    human_judgment: false
  - id: D6
    description: "O script consome as tres rotas de administracao (listagem, criacao, alternancia de atividade) e o clique e tratado por delegacao, sem manipulador embutido na marcacao"
    requirement: "L-07"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_front_consome_as_rotas_de_administracao"
        status: pass
      - kind: unit
        ref: "test_smoke.py#test_front_nao_usa_manipulador_embutido_na_marcacao"
        status: pass
    human_judgment: false
  - id: D7
    description: "Criterio de pronto da fase (SPEC S15): vendedor recebe 403 nas tres rotas de administracao chamadas direto pela API, sem navegador, mesmo com a secao de admin escondida na tela"
    requirement: "L-07"
    verification:
      - kind: e2e
        ref: "test_smoke.py#test_area_de_admin_escondida_nao_e_o_controle_de_acesso"
        status: pass
    human_judgment: false
  - id: D8
    description: "A tela de login, o painel de historico e a area de administracao funcionam de ponta a ponta no navegador (fluxo visual completo: login, geracao de briefing, historico atualizando, admin criando/desativando usuario)"
    verification: []
    human_judgment: true
    rationale: "Os testes automatizados provam o contrato de rede (rotas consumidas, escape aplicado, guarda no servidor) e o HTML servido, mas a renderizacao real no navegador e a interacao visual (troca de tela, mensagens de erro autoradas aparecendo no lugar certo, formulario limpando apos sucesso) dependem de julgamento humano — nao ha suite de UI automatizada neste projeto (L-10, sem framework, sem Playwright)."

duration: 27min
completed: 2026-08-27
status: complete
---

# Phase 6 Plan 5: Tela de login, historico e area de administracao Summary

**UI existente (static/index.html) estendida em JavaScript puro para desenhar tela de login, estado autenticado, painel de historico com recorte por papel e area de administracao — escapar() agora cobre cinco caracteres, e o teste de fechamento da fase prova que esconder a area de admin nunca foi o controle de acesso.**

## Performance

- **Duration:** 27 min (aprox.)
- **Started:** 2026-08-27T18:15:00Z (aprox.)
- **Completed:** 2026-08-27T18:42:01Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- `escapar()` estendido de quatro para cinco caracteres — a aspa simples agora mapeia para `&#39;`, fechando o unico ponto do arquivo que interpola valor dentro de atributo (o id do usuario no botao de ativar/desativar). As oito chamadas existentes continuam inalteradas.
- Duas `<main>` na mesma pagina: `id="login"` (usuario, senha mascarada, botao de entrar) e `id="app"` (formulario de briefing existente + painel de historico + area de admin), alternadas via `hidden` a partir de `GET /api/auth/me`. Cabecalho ganha identificacao do usuario logado e botao de sair.
- `carregarSessao()` e a unica fonte de verdade do que a tela desenha: 200 mostra a aplicacao e carrega historico (e usuarios, se admin); 401 devolve a tela de login; qualquer outro status mostra falha autorada. Chamada no carregamento da pagina, apos login, apos logout, e reaproveitada quando o historico recebe 401 no meio do uso.
- Painel de historico (`carregarHistorico()`) consome `GET /api/historico`, mostra endereco/extrator/data de coleta, e a coluna de dono so quando o usuario logado e admin — linha sem dono mostra marcador textual, nunca valor bruto nulo. Todo valor da API passa por `escapar()`.
- Area de administracao (`carregarUsuarios()`) oculta por `hidden`, exibida so para admin, com comentario explicito no codigo de que isso e conforto de uso e nao controle de acesso (L-07). Lista de usuarios com alternancia de atividade por delegacao de clique (sem manipulador embutido); formulario de criacao com selecao fechada nos dois papeis de L-08.
- Nove testes novos em `test_smoke.py`, incluindo o teste de fechamento da fase: vendedor autenticado recebe 403 nas tres rotas de administracao chamadas direto pela API, sem navegador (SPEC S15, L-07).
- Suite completa passa de 45 para 54 testes, sem nenhuma regressao. `requirements.txt` intocado (L-06/L-10 — nenhum pacote novo).

## Task Commits

Each task was committed atomically:

1. **Task 1: Tela de login, estado autenticado e escapar() cobrindo aspas simples (L-07, L-10, D-16)** - `6f55d08` (feat)
2. **Task 2: Painel de historico — o vendedor ve o proprio, o admin ve tudo (D-18, L-10)** - `aa90c63` (feat)
3. **Task 3: Area de administracao — usuarios, criacao e ativacao (L-07, L-08, D-17)** - `cf2281e` (feat)

_Nota: as tres tasks deste plano sao `type="auto"` — cada uma segue o protocolo de commit atomico unico ja usado nos demais planos da fase (implementacao real + `<verify>` real num commit so)._

## Files Created/Modified

- `static/index.html` - `escapar()` cobrindo cinco caracteres; secao de login (`id="login"`) com campo de senha mascarado; identificacao do usuario e botao de sair no cabecalho; contenedor da aplicacao (`id="app"`) controlado por `hidden`; `carregarSessao()`; painel de historico (`id="painel-historico"`) com `carregarHistorico()`; secao de administracao (`id="admin"`) com lista de usuarios, alternancia de atividade por delegacao de clique e formulario de criacao (`carregarUsuarios()`)
- `test_smoke.py` - Nove testes novos: `test_pagina_inicial_traz_tela_de_login`, `test_escapar_do_front_cobre_aspas_simples`, `test_front_nao_desliga_o_envio_de_cookie`, `test_front_consome_as_rotas_de_sessao`, `test_front_consome_a_rota_de_historico`, `test_vendedor_logado_recebe_apenas_o_proprio_historico_pela_api`, `test_front_consome_as_rotas_de_administracao`, `test_front_nao_usa_manipulador_embutido_na_marcacao`, `test_area_de_admin_escondida_nao_e_o_controle_de_acesso`

## Decisions Made

**Duas `<main>` na mesma pagina, nao uma unica arvore condicional.** O HTML5 permite multiplas `<main>` desde que no maximo uma esteja visivel por vez (as demais com `hidden`). Optei por reaproveitar a tag semantica em vez de introduzir uma `<div>` extra so para o estado de login, porque mantem a mesma disciplina de estilo (`main { max-width:820px; ... }`) sem nenhuma regra CSS nova alem da unica permitida pelo plano (estilo de `input`/`select`).

**`carregarHistorico()` e `carregarUsuarios()` chamados dentro do caminho de sucesso de `carregarSessao()`**, nao amarrados a eventos separados — evita a corrida entre "sessao confirmada" e "dado carregado" que existiria se cada painel disparasse sua propria checagem de sessao.

**Clique de ativar/desativar usuario por delegacao de evento** a partir do contenedor da lista (`listaUsuarios.addEventListener('click', ...)`), lendo o id do `dataset` do elemento — fecha T-06-48 (manipulador embutido na marcacao) sem precisar de framework, mesmo padrao que qualquer lista futura renderizada por template literal com acao por item pode reutilizar.

**Nenhum pacote novo instalado** — `git diff --name-only requirements.txt` vazio, confirmado apos as tres tasks (L-06/L-10).

## Deviations from Plan

None - plan executed exactly as written. As tres tasks seguiram a acao descrita no PLAN.md sem desvio de escopo, arquivo ou regra. Nenhuma rota de servidor (`app/*.py`) foi tocada; `SPEC-sales-intel.md` nao foi editada (fora de escopo deste plano).

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. A UI consome rotas ja existentes e testadas dos planos 06-01/06-03/06-04; nao ha variavel de ambiente nova nem configuracao de servico externo.

## Next Phase Readiness

- **Fase 6 completa.** As seis entradas do escopo (login, dois papeis, vendedor ve o proprio historico, admin gerencia usuarios, toda rota valida papel no servidor, tela de login e area de admin na UI existente) estao implementadas e testadas.
- Criterio de pronto da SPEC S15 fechado tanto no servidor (plano 06-04, `test_inventario_de_rotas_declara_guarda_para_cada_rota`) quanto na UI (este plano, `test_area_de_admin_escondida_nao_e_o_controle_de_acesso`): esconder a area de admin na tela nunca foi o controle de acesso.
- Suite completa: 54 testes, offline, sem nenhuma regressao acumulada nas cinco tasks da fase.
- Verificacao visual no navegador (login real, geracao de briefing, historico atualizando, admin criando/desativando usuario) fica para verificacao humana (UAT) — nao ha suite de UI automatizada neste projeto (L-10, sem framework, sem passo de build, sem Playwright instalado).
- Sem bloqueios.

---
*Phase: 06-auth*
*Completed: 2026-08-27*

## Self-Check: PASSED

- FOUND: `static/index.html`
- FOUND: `test_smoke.py`
- FOUND: `.planning/phases/06-auth/06-05-SUMMARY.md`
- FOUND commit: `6f55d08`
- FOUND commit: `aa90c63`
- FOUND commit: `cf2281e`
- FOUND commit: `9f04642`
- `python -m pytest -q` — 54 passed, 0 failed
