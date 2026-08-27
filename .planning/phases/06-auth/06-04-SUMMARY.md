---
phase: 06-auth
plan: 04
subsystem: auth
tags: [scrypt, sqlite, fastapi-depends, session-revocation, route-inventory, env-bootstrap]

# Dependency graph
requires:
  - phase: 06-auth (plano 06-01)
    provides: "app/auth.py completo (scrypt, sessao opaca), dependencias usuario_atual/exigir_admin, helper de teste _cliente_autenticado"
  - phase: 06-auth (plano 06-02)
    provides: "SPEC-sales-intel.md S10 com as duas rotas de admin ja documentadas antes do codigo, S13 com ADMIN_USERNAME/ADMIN_SENHA sem valor"
  - phase: 06-auth (plano 06-03)
    provides: "app/db.py com briefings.owner e db.listar(dono=, ver_tudo=) fail-closed, guardas em POST /api/briefings e GET /api/historico"
provides:
  - "app/config.py: admin_username()/admin_senha(), funcoes sem valor padrao"
  - "app/auth.py: TAM_MINIMO_SENHA, semear_admin_inicial() idempotente e com falha alta para senha curta, encerrar_sessoes_do_usuario(), definir_ativo() que revoga sessao ao desativar"
  - "app/schemas.py: CriarUsuarioRequest (papel fechado por Literal) e AlterarAtivoRequest"
  - "app/main.py: inicializar() chamando o seed; POST /api/admin/usuarios e POST /api/admin/usuarios/{usuario_id}/ativo, ambas sob exigir_admin"
  - ".env.example: ADMIN_USERNAME= e ADMIN_SENHA= sem valor"
  - "test_smoke.py: GUARDAS_ESPERADAS, _guardas_da_rota(), treze testes novos fechando o inventario de rotas do D-17"
affects: [06-05]

# Actuals (#2632)
actuals:
  tokens: 5725
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bootstrap por variavel de ambiente dentro do unico gancho de subida existente (inicializar()), no molde de funcao-nao-constante de config.py"
    - "Revogacao imediata de sessao: definir_ativo(falso) chama encerrar_sessoes_do_usuario na mesma operacao, nunca so a coluna"
    - "Inventario de rotas travado por teste: igualdade de conjuntos entre rotas reais (filtradas por hasattr(r,'dependant')) e um dicionario declarado, com percurso recursivo do grafo de Depends para compor guardas encadeadas"

key-files:
  created: []
  modified:
    - app/config.py
    - app/auth.py
    - app/schemas.py
    - app/main.py
    - test_smoke.py
    - .env.example

key-decisions:
  - "D-19 aplicada exatamente como travada: sem valor padrao em nenhum ponto do modulo; falha alta (RuntimeError) para senha curta, com mensagem que nunca ecoa a senha; idempotente (nao troca senha nem promove papel de usuario existente)"
  - "TAM_MINIMO_SENHA=12 e reutilizado como min_length de CriarUsuarioRequest.senha — a politica de senha do seed e da criacao de usuario pela API e uma so, nao duas politicas divergentes"
  - "GUARDAS_ESPERADAS usa tres rotulos (publico/autenticado/restrito_admin) e exige, para rotulo restrito, tanto exigir_admin quanto usuario_atual no grafo — a composicao de dependencias (exigir_admin -> usuario_atual) so aparece com recursao, documentada no proprio helper"
  - "Known trap do plano confirmado outra vez: getattr(r, 'methods', None) tambem casa com /docs, /redoc e /openapi.json (Route puro do Starlette sem .dependant); o teste usa hasattr(r, 'dependant') para filtrar apenas rotas decoradas, que exclui essas tres e o mount de estaticos ao mesmo tempo — decisao deliberada de manter as rotas de documentacao do framework fora do inventario de D-17 (mesma disposicao ja registrada como accept/T-06-44 no threat model do plano)"
  - "Gap fechado, sem discrepancia: SPEC S10 (plano 06-02) ja documentava POST /api/admin/usuarios e POST /api/admin/usuarios/{usuario_id}/ativo antes deste plano existir em codigo; apos a Task 2, as duas rotas existem em app/main.py com o mesmo metodo, caminho e guarda (exigir_admin) que a SPEC ja descrevia — o teste de inventario da Task 3 confere isso em codigo, e a SPEC nao precisou de nenhuma edicao"

patterns-established:
  - "Seed de primeiro-acesso: variavel de ambiente lida por funcao (nunca constante), chamada dentro do gancho de subida ja existente, idempotente por checagem de existencia antes de escrever"
  - "Par de revogacao: qualquer mudanca de estado que reduza privilegio/acesso de um usuario (aqui, ativo=False) precisa, na mesma operacao, encerrar as sessoes vivas — nao apenas mudar a coluna que `validar_sessao` consulta"

requirements-completed: [L-06, L-07, L-08, D-17, D-19, SPEC-8, SPEC-10, SPEC-13]

coverage:
  - id: D1
    description: "Bootstrap do primeiro admin a partir de ADMIN_USERNAME/ADMIN_SENHA na subida do processo, sem senha default no codigo (D-19)"
    requirement: "D-19"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_semear_admin_inicial_cria_admin_a_partir_do_ambiente"
        status: pass
    human_judgment: false
  - id: D2
    description: "Sem as duas variaveis de ambiente (ou so uma delas), nenhum admin e criado e o processo sobe normalmente"
    requirement: "D-19"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_sem_variaveis_de_ambiente_nenhum_admin_e_criado"
        status: pass
    human_judgment: false
  - id: D3
    description: "Reiniciar o processo com um admin/usuario ja existente do mesmo username nao troca a senha nem o papel dele"
    requirement: "D-19"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_semear_admin_inicial_nao_troca_senha_nem_papel_de_usuario_existente"
        status: pass
    human_judgment: false
  - id: D4
    description: "Senha de admin abaixo de 12 caracteres levanta RuntimeError com mensagem autorada que nunca ecoa a senha"
    requirement: "D-19"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_senha_de_admin_curta_levanta_com_mensagem_autorada"
        status: pass
    human_judgment: false
  - id: D5
    description: "Admin cria um vendedor pela API (POST /api/admin/usuarios) e o vendedor consegue logar em seguida com a senha informada"
    requirement: "L-07"
    verification:
      - kind: e2e
        ref: "test_smoke.py#test_admin_cria_vendedor_e_o_vendedor_consegue_logar"
        status: pass
    human_judgment: false
  - id: D6
    description: "Vendedor chamando POST /api/admin/usuarios recebe 403; sem sessao recebe 401; username duplicado recebe 409 sem vazar erro do banco"
    requirement: "L-07"
    verification:
      - kind: e2e
        ref: "test_smoke.py#test_criar_usuario_com_sessao_de_vendedor_devolve_403"
        status: pass
      - kind: e2e
        ref: "test_smoke.py#test_criar_usuario_sem_sessao_devolve_401"
        status: pass
      - kind: e2e
        ref: "test_smoke.py#test_username_duplicado_devolve_409_com_mensagem_autorada"
        status: pass
    human_judgment: false
  - id: D7
    description: "Desativar um usuario com sessao viva derruba a sessao na hora (401 na proxima chamada do mesmo cliente); reativado, ele loga de novo; admin nao pode desativar a si mesmo"
    requirement: "D-16"
    verification:
      - kind: e2e
        ref: "test_smoke.py#test_desativar_usuario_derruba_a_sessao_viva"
        status: pass
      - kind: e2e
        ref: "test_smoke.py#test_admin_nao_pode_desativar_a_si_mesmo"
        status: pass
    human_judgment: false
  - id: D8
    description: "Toda rota da aplicacao aparece num inventario declarado com a guarda que aplica; uma rota nao declarada quebra a suite (D-17, fecha o aceite R-01)"
    requirement: "D-17"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_inventario_de_rotas_declara_guarda_para_cada_rota"
        status: pass
    human_judgment: false
  - id: D9
    description: "Nenhuma rota le ou grava configuracao do processo; /health e / continuam publicos sem cookie (RF13, R-08/R-11 renovados)"
    requirement: "SPEC-10"
    verification:
      - kind: unit
        ref: "test_smoke.py#test_rotas_publicas_respondem_sem_cookie"
        status: pass
      - kind: unit
        ref: "test_smoke.py#test_nenhuma_rota_expoe_configuracao_do_processo"
        status: pass
    human_judgment: false
  - id: D10
    description: "Suite completa sem regressao: 45 testes passam (32 da baseline + 13 novos deste plano), requirements.txt intocado"
    verification:
      - kind: unit
        ref: "python -m pytest -q — 45 passed"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-08-27
status: complete
---

# Phase 6 Plan 4: Bootstrap de admin, gestao de usuarios e inventario de rotas travado Summary

**Primeiro admin semeado de ADMIN_USERNAME/ADMIN_SENHA no boot (sem senha default), admin cria e desativa vendedores com revogacao imediata de sessao, e um inventario de dez rotas travado por teste de igualdade de conjuntos fecha formalmente o aceite R-01 da Fase 5 (D-17).**

## Performance

- **Duration:** 35 min (aprox.)
- **Started:** 2026-08-27T19:00:00Z (aprox.)
- **Completed:** 2026-08-27T19:35:00Z (aprox.)
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `app/config.py::admin_username()`/`admin_senha()` — funcoes (nao constantes) que leem o ambiente em tempo de chamada, sem valor padrao em ponto algum, cumprindo D-19.
- `app/auth.py::semear_admin_inicial()` — idempotente (nunca troca senha nem promove papel de usuario existente), com falha alta autorada quando `ADMIN_SENHA` tem menos de `TAM_MINIMO_SENHA=12` caracteres, e devolvendo `None` em silencio quando falta qualquer uma das duas variaveis. Ligada em `inicializar()`, logo apos `db.criar_tabelas()`.
- `app/schemas.py::CriarUsuarioRequest`/`AlterarAtivoRequest` — `papel` fechado por `Literal["vendedor","admin"]` (L-08), senha com o mesmo minimo de 12 caracteres do seed.
- `app/auth.py::definir_ativo()`/`encerrar_sessoes_do_usuario()` — desativar um usuario chama a revogacao na mesma operacao, fechando a janela em que uma sessao viva sobreviveria a desativacao.
- `app/main.py::cadastrar_usuario` (`POST /api/admin/usuarios`) e `alterar_ativo` (`POST /api/admin/usuarios/{usuario_id}/ativo`) — as duas rotas que a SPEC S10 (plano 06-02) ja documentava antes de existirem em codigo, ambas sob `exigir_admin`; 409 sem vazar erro do banco na duplicidade, 400 contra auto-desativacao, 404 para id desconhecido.
- `.env.example` ganha `ADMIN_USERNAME=` e `ADMIN_SENHA=` sem nenhum valor de exemplo.
- `test_smoke.py::GUARDAS_ESPERADAS` + `_guardas_da_rota()` + `test_inventario_de_rotas_declara_guarda_para_cada_rota` — dez rotas decoradas, igualdade de conjuntos, percurso recursivo do grafo de `Depends` para capturar guardas compostas (`exigir_admin` -> `usuario_atual`). Mais dois testes fechando `/health`/`/` publicos e a ausencia de rota de configuracao (aceites R-08/R-11 renovados e agora travados por teste, nao so por leitura).
- Treze testes novos ao todo; suite completa passa de 32 para 45 testes, sem nenhuma regressao.

## Task Commits

Each task was committed atomically:

1. **Task 1: Primeiro admin semeado do ambiente, sem senha embutida (D-19, L-06)** - `b646aa9` (feat)
2. **Task 2: Admin cria e desativa usuarios, e desativar derruba a sessao viva (L-07, L-08, D-16, D-17)** - `fdcb6af` (feat)
3. **Task 3: Inventario de rotas com guarda declarada, travado por teste (D-17, L-07)** - `52552a5` (test)

_Nota: as tres tasks deste plano sao `tdd="true"` mas do tipo `auto` — cada uma segue o protocolo de commit atomico unico ja usado nos planos 06-01/06-03 (implementacao real + `<verify>` real num commit so), nao o ciclo RED/GREEN/REFACTOR de tres commits._

## Files Created/Modified

- `app/config.py` - `admin_username()`, `admin_senha()`
- `app/auth.py` - `TAM_MINIMO_SENHA`, `MSG_SENHA_DE_ADMIN_CURTA`, `semear_admin_inicial()`, `encerrar_sessoes_do_usuario()`, `definir_ativo()`
- `app/schemas.py` - `CriarUsuarioRequest`, `AlterarAtivoRequest`
- `app/main.py` - `inicializar()` chamando o seed; literais `MSG_USERNAME_EM_USO`/`MSG_USUARIO_NAO_ENCONTRADO`/`MSG_NAO_PODE_DESATIVAR_A_SI_MESMO`; `cadastrar_usuario`; `alterar_ativo`
- `.env.example` - `ADMIN_USERNAME=`, `ADMIN_SENHA=`
- `test_smoke.py` - Treze testes novos: quatro do seed (Task 1), seis de gestao de usuario e revogacao (Task 2), tres do inventario de rotas (Task 3)

## Decisions Made

- D-19, D-16, D-17, L-08 aplicadas exatamente como travadas em `06-CONTEXT.md` — ver `key-decisions` no frontmatter para o detalhe de cada uma.
- **Gap do plano 06-02 fechado, sem discrepancia entre SPEC e codigo.** A SPEC S10 ja documentava as duas rotas de admin antes deste plano existir em codigo (decisao deliberada do 06-02, registrada no proprio `06-02-SUMMARY.md`). Apos a Task 2, `POST /api/admin/usuarios` e `POST /api/admin/usuarios/{usuario_id}/ativo` existem em `app/main.py` com o mesmo metodo, caminho e guarda (`exigir_admin`) que a SPEC ja descrevia. O teste de inventario de rotas da Task 3 confere isso formalmente em codigo — nao houve necessidade de editar `SPEC-sales-intel.md` (fora de escopo deste plano de qualquer forma).
- **Known trap confirmado outra vez.** `getattr(r, 'methods', None)` tambem casa com `/docs`, `/redoc` e `/openapi.json` (routes puras do Starlette sem `.dependant`) — o mesmo problema que o plano 06-03 documentou. O teste de inventario usa `hasattr(r, 'dependant')` para filtrar, o que exclui essas tres rotas do framework **e** o mount de estaticos ao mesmo tempo, num unico filtro. Decisao deliberada: as rotas de documentacao do FastAPI ficam fora do inventario de D-17, coerente com a disposicao ja registrada como `accept`/T-06-44 no threat model do proprio plano (expõem so a forma do contrato, nunca dado de negocio).
- `TAM_MINIMO_SENHA=12` foi reutilizado como `min_length` de `CriarUsuarioRequest.senha`, em vez de duas constantes separadas — a politica de senha do seed e da criacao de usuario pela API e uma so.

## Deviations from Plan

None - plan executed exactly as written. As tres tasks seguiram a acao descrita no PLAN.md sem desvio de escopo, arquivo ou regra.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. `ADMIN_USERNAME`/`ADMIN_SENHA` ficam vazias em `.env.example` por desenho (D-19); quem for rodar a aplicacao com um admin precisa preencher essas duas variaveis no proprio `.env` local (nao versionado), fora do escopo de execucao deste plano. Nenhum pacote novo foi instalado (`git diff --name-only requirements.txt` vazio, confirmado apos as tres tasks).

## Next Phase Readiness

- Servidor fechado: existe primeiro acesso sem cadastro publico e sem credencial no repositorio (D-19), admin gerencia vendedores com revogacao imediata (D-16), e o inventario de rotas trava D-17/L-07 em teste executavel — o aceite R-01 da Fase 5 esta formalmente fechado, e a promessa que sustenta R-11 esta verificada por codigo, nao so escrita.
- Plano 06-05 (UI de login/historico/admin em `static/index.html`) pode prosseguir sem nenhum ajuste retroativo neste plano: as rotas que a UI vai consumir (`POST /api/admin/usuarios`, `POST /api/admin/usuarios/{usuario_id}/ativo`, mais tudo dos planos 06-01/06-03) ja existem, testadas, e com a guarda que a SPEC S10 promete.
- Sem bloqueios.

---
*Phase: 06-auth*
*Completed: 2026-08-27*
