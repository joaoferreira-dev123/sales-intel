---
phase: 06-auth
verified: 2026-08-27T18:56:45Z
status: human_needed
score: 19/19 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Abrir a UI num navegador real: logar como vendedor, confirmar que a secao de admin (#admin) nunca aparece no DOM renderizado, colar um link e ler o cartao de briefing; depois logar como admin e confirmar que a tela de gerenciar usuarios (listar, criar, ativar/desativar) funciona visualmente de ponta a ponta, incluindo o botao de sair."
    expected: "Fluxo visual completo funciona sem erro de console; a area de admin so aparece para o papel admin; nenhum HTML quebrado ou nao escapado aparece na tela mesmo com um username contendo aspas simples."
    why_human: "test_pagina_inicial_traz_tela_de_login, test_escapar_do_front_cobre_aspas_simples e os testes 'front_consome_*' verificam presenca de marcacao/JS e chamadas de rede via regex/parse estatico e um TestClient que nao executa JavaScript — nenhum deles renderiza a pagina num motor de browser real, entao a experiencia visual (estado de carregamento, layout, foco do teclado, comportamento real do fetch com cookies no navegador) nao tem evidencia automatizada nesta verificacao."
---

# Phase 6: Auth Verification Report

**Phase Goal (SPEC §15):** Login, papeis, protecao das rotas no servidor, tela de admin com
historico. Pronto quando: vendedor nao acessa rota de admin nem chamando a API direto.
**Verified:** 2026-08-27T18:56:45Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Nota de processo

Este projeto nao tem `ROADMAP.md`/`STATE.md`/`PROJECT.md`/`REQUIREMENTS.md`, por decisao
explicita ja estabelecida na Fase 5. Os must-haves desta verificacao vem de
`.planning/phases/06-auth/06-CONTEXT.md` (os seis itens de escopo declarados) e de
`SPEC-sales-intel.md` §8, §10, §13, §15 (modelo de dados, contrato de rotas, variaveis de
ambiente, criterio de pronto). Ausencia desses quatro arquivos nao e reportada como gap.

## Goal Achievement

### R-01 done-criterion (SPEC §15) — verificado ao vivo, sem navegador

Script descartavel (`TestClient` real, sem mocks de auth, banco em `tmp_path`) que dirige a
API diretamente: cria um usuario `vendedor` e um `admin` via `auth.criar_usuario`, loga os
dois pela rota real `POST /api/auth/login` (nao fabrica cookie), e chama as tres rotas
admin com a sessao do vendedor.

```
no-session GET /api/admin/usuarios: 401
no-session POST /api/admin/usuarios: 401
no-session POST /api/admin/usuarios/{id}/ativo: 401
login vendedor: 200 {...}
cookie set: True
vendedor-session GET /api/admin/usuarios: 403
vendedor-session POST /api/admin/usuarios: 403
vendedor-session POST /api/admin/usuarios/{id}/ativo: 403
vendedor GET /api/auth/me: 200 (papel: vendedor)
vendedor GET /api/historico: 200
vendedor spoof header X-Papel: admin: 403 (header do cliente e ignorado, papel vem so da sessao)
admin-session GET /api/admin/usuarios: 200
ALL CHECKS PASSED
```

Sem sessao: 401 nas tres rotas. Com sessao de vendedor: 403 nas tres rotas, inclusive
tentando forjar um header `X-Papel: admin` (ignorado — o servidor le o papel exclusivamente
da linha de sessao/usuario, nunca de um campo do cliente). Com sessao de admin: 200. Isto
corrobora, por evidencia direta e independente (nao reexecutando os testes do plano), o
mesmo resultado que `test_vendedor_autenticado_recebe_403_em_rota_de_admin`,
`test_rota_de_admin_sem_cookie_devolve_401` e
`test_area_de_admin_escondida_nao_e_o_controle_de_acesso` ja travam em `test_smoke.py`.
**R-01 (aceite adiado pela Fase 5) esta genuinamente fechado.**

### Observable Truths — seis itens de escopo declarados (06-CONTEXT.md)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Login com usuario e senha, senha guardada com hash forte | ✓ VERIFIED | `app/auth.py::gerar_hash_senha`/`verificar_senha` (scrypt, `n=2**14,r=8,p=1,dklen=32`, salt de 16 bytes por `secrets.token_bytes`, comparacao via `hmac.compare_digest`); `test_hash_de_senha_usa_scrypt_com_salt_por_usuario` passa; confirmado por leitura direta de `app/auth.py:54-95` |
| 2 | Dois papeis: `vendedor` e `admin` | ✓ VERIFIED | `Usuario.papel: Literal["vendedor","admin"]` (`schemas.py:95`); `CriarUsuarioRequest.papel` mesmo Literal (`schemas.py:110`); nenhum terceiro papel em nenhuma rota de escrita. Ressalva nao-bloqueante: sem `CHECK` no schema do banco — ver Warnings abaixo (WR-02) |
| 3 | Vendedor gera briefing e ve o proprio historico | ✓ VERIFIED | `POST /api/briefings` grava `dono=usuario.id` (`main.py:398`); `GET /api/historico` ramifica por `usuario.papel` (`main.py:458-460`); `db.listar(dono=...)` nunca casa linha de outro dono nem linha sem dono (`db.py:164-176`); `test_vendedor_ve_apenas_o_proprio_historico` e `test_linha_sem_dono_so_aparece_para_admin` passam; reproduzido nesta verificacao (ver script acima, rota `/api/historico` volta 200 para o vendedor autenticado) |
| 4 | Admin ve tudo e gerencia usuarios | ✓ VERIFIED | `db.listar(ver_tudo=True)` inclui linhas com `owner` nulo (`db.py:152-163`); `GET/POST /api/admin/usuarios` e `POST /api/admin/usuarios/{id}/ativo` sob `exigir_admin`; `test_admin_cria_vendedor_e_o_vendedor_consegue_logar`, `test_desativar_usuario_derruba_a_sessao_viva`, `test_admin_nao_pode_desativar_a_si_mesmo` passam; reproduzido nesta verificacao (sessao admin -> 200 em `GET /api/admin/usuarios`) |
| 5 | Toda rota da API valida papel no servidor a cada requisicao | ✓ VERIFIED | `test_inventario_de_rotas_declara_guarda_para_cada_rota` percorre `main.app.routes` e o grafo `.dependant` recursivamente, com igualdade de conjunto (nao inclusao) contra as 10 rotas decoradas — uma rota nova sem entrada quebra o teste por desenho; `usuario_atual`/`exigir_admin` confirmados via `Depends` em cada rota autenticada/restrita (`main.py:153-283`) |
| 6 | Tela de login e area de admin dentro da UI existente | ✓ VERIFIED | `static/index.html` (vanilla JS, sem framework, sem build step): secao `#login` (linha 49), secao `#admin` (linha 81), chamadas `fetch` para `/api/auth/*` e `/api/admin/*`; `test_pagina_inicial_traz_tela_de_login` e `test_front_consome_as_rotas_de_administracao` passam. Comportamento visual real em navegador nao verificado por este agente — ver Human Verification |

**Score desta secao:** 6/6 (1 com ressalva nao-bloqueante documentada em Warnings)

### Observable Truths — must_haves consolidados dos 5 planos (06-01..06-05)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 7 | Vendedor autenticado chamando `GET /api/admin/usuarios` direto recebe 403 | ✓ VERIFIED | `test_vendedor_autenticado_recebe_403_em_rota_de_admin` passa; reproduzido ao vivo nesta verificacao |
| 8 | Chamada sem cookie a rota admin ou `/api/auth/me` recebe 401 | ✓ VERIFIED | `test_rota_de_admin_sem_cookie_devolve_401` passa; reproduzido ao vivo |
| 9 | Usuario inexistente e senha errada produzem exatamente a mesma resposta (401 + mesma frase) | ✓ VERIFIED | `MSG_LOGIN_INVALIDO` unico literal usado nos dois ramos (`auth.py:44,201-204`); `test_login_invalido_nao_distingue_usuario_inexistente_de_senha_errada` passa. Ressalva de timing no ramo "usuario inativo" — ver WR-01 abaixo (nao invalida esta truth, que cobre inexistente vs senha errada, nao inativo) |
| 10 | Cookie de sessao com `HttpOnly`/`SameSite=Lax`; banco guarda sha256 do token, nunca o token bruto | ✓ VERIFIED | `main.py:212-223` (`httponly=True, samesite="lax"`); `auth.py:191` (`hashlib.sha256(token...)` antes do INSERT); leitura direta confirma que `token` bruto nunca e persistido, so devolvido no `Set-Cookie` |
| 11 | `POST /api/auth/logout` apaga a sessao; chamada seguinte volta 401 | ✓ VERIFIED | `test_logout_invalida_a_sessao` passa |
| 12 | SPEC §8/§10/§13 refletem o codigo real (D-15 divergencia registrada) | ✓ VERIFIED | `SPEC-sales-intel.md` §8 documenta `scrypt$n$r$p$salt$chave` e a divergencia de D-15 explicitamente (linhas 163-168 do documento lido); §10 lista as 11 linhas (10 rotas decoradas + `/static/*`); §13 lista `ADMIN_USERNAME`/`ADMIN_SENHA` sem valor de exemplo |
| 13 | `/api/briefings` e `/api/historico` sem cookie devolvem 401 | ✓ VERIFIED | `test_briefings_sem_cookie_devolve_401`, `test_historico_sem_cookie_devolve_401` passam |
| 14 | `db.listar` sem `dono` e sem `ver_tudo` devolve lista vazia (fail-closed) | ✓ VERIFIED | `db.py:178-181` ramo explicito `return []`; `test_listar_sem_dono_e_sem_ver_tudo_devolve_lista_vazia` passa |
| 15 | Recoletar URL ja coletada por outro vendedor nao transfere o dono | ✓ VERIFIED | `ON CONFLICT(url) DO UPDATE` no `db.py:130-133` nao inclui `owner` na clausula; `test_recoleta_da_mesma_url_por_outro_dono_nao_troca_o_dono` passa |
| 16 | Nenhuma linha existente de `briefings` e removida/reescrita pela coluna nova | ✓ VERIFIED | `ALTER TABLE briefings ADD COLUMN owner TEXT` condicional a PRAGMA (`db.py:76-80`), sem `DROP`/`DELETE`; `test_criar_tabelas_e_repetivel_e_preserva_linhas_antigas` passa |
| 17 | Bootstrap do primeiro admin via `ADMIN_USERNAME`/`ADMIN_SENHA`, sem senha default no codigo | ✓ VERIFIED | `auth.semear_admin_inicial` le `config.admin_username()`/`admin_senha()`, sem literal default (`auth.py:250-282`); `test_semear_admin_inicial_cria_admin_a_partir_do_ambiente`, `test_sem_variaveis_de_ambiente_nenhum_admin_e_criado`, `test_semear_admin_inicial_nao_troca_senha_nem_papel_de_usuario_existente`, `test_senha_de_admin_curta_levanta_com_mensagem_autorada` passam |
| 18 | Desativar usuario derruba a sessao viva dele | ✓ VERIFIED | `auth.definir_ativo` chama `encerrar_sessoes_do_usuario` no ramo de desativacao (`auth.py:311-312`); `test_desativar_usuario_derruba_a_sessao_viva` passa |
| 19 | Nenhuma rota le/grava configuracao do processo (R-11 renovado) | ✓ VERIFIED | `test_nenhuma_rota_expoe_configuracao_do_processo` confere ausencia de `import os`, `LLM_BASE_URL`, `LLM_MODELO` em `app/main.py` fora de comentarios; leitura direta confirma `app/main.py` nao importa `os` |

**Score desta secao:** 13/13

**Score total:** 19/19 truths verificadas (nenhuma comportamental-nao-verificada; a unica
ressalva legitima — comportamento visual em navegador real — vai para `human_verification`,
nao para uma truth marcada FAILED)

### SPEC §10 route inventory vs running app — a diferenca de 11 vs 10 e entendida, nao um buraco

`SPEC-sales-intel.md` §10 lista 11 linhas (10 rotas decoradas + `GET /static/*`).
`test_inventario_de_rotas_declara_guarda_para_cada_rota` cobre exatamente as 10 rotas
decoradas (`hasattr(r, "dependant")`), porque `/static/*` e um `StaticFiles` mount do
Starlette (classe `Mount`), sem `.dependant` — nao existe grafo de dependencia do FastAPI
para percorrer nesse tipo de rota. O comentario do proprio teste (`test_smoke.py:891-898`)
documenta essa exclusao explicitamente e aponta para o teste companheiro
`test_rotas_publicas_respondem_sem_cookie`, que confirma separadamente que o mount de
estaticos continua ativo (`isinstance(getattr(r, "app", None), StaticFiles)`). Alem disso,
o diretorio `static/` contem apenas `index.html` (confirmado por listagem), entao nao ha
nenhum outro arquivo estatico que pudesse carregar dado de negocio sem guarda. **Veredito:
gap entendido e coberto por teste complementar, nao um buraco real de autorizacao.**

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `app/auth.py` | Nucleo de auth (hash, sessao, seed, ativacao) | ✓ VERIFIED | Todas as funcoes declaradas nos `must_haves` dos 5 planos presentes e substantivas: `gerar_hash_senha`, `verificar_senha`, `criar_usuario`, `buscar_usuario_por_id/username`, `listar_usuarios`, `autenticar`, `criar_sessao`, `validar_sessao`, `encerrar_sessao`, `semear_admin_inicial`, `encerrar_sessoes_do_usuario`, `definir_ativo` |
| `app/db.py` (tabelas `usuarios`/`sessoes`, coluna `owner`) | Schema novo, aditivo | ✓ VERIFIED | `criar_tabelas()` cria as duas tabelas novas e adiciona `owner` via PRAGMA guard; `listar()`/`salvar()` com os parametros `dono`/`ver_tudo`/`dono=` |
| `app/main.py` (`usuario_atual`, `exigir_admin`, rotas de auth/admin) | Dependencias FastAPI (D-17) + rotas | ✓ VERIFIED | `usuario_atual`/`exigir_admin` (linhas 153-173); rotas `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`, `/api/admin/usuarios` (GET/POST), `/api/admin/usuarios/{id}/ativo` presentes e ligadas |
| `app/schemas.py` (`LoginRequest`, `Usuario`, `CriarUsuarioRequest`, `AlterarAtivoRequest`) | Contratos Pydantic | ✓ VERIFIED | Todos presentes, `papel` fechado por `Literal` |
| `app/config.py` (`admin_username`, `admin_senha`) | Leitura de ambiente (D-19) | ✓ VERIFIED | Funcoes presentes, sem valor default |
| `static/index.html` (`#login`, `#admin`, `escapar()`) | UI de login/admin | ✓ VERIFIED | Secoes presentes; `escapar()` cobre `&<>"'` (5 caracteres, linha 393-396) |
| `test_smoke.py` | Testes de auth/admin/UI | ✓ VERIFIED | 39 testes novos de Fase 6 (linhas 474-1121), todos mapeados aos must-haves acima; `pytest -q` roda 54/54 |
| `SPEC-sales-intel.md` §8/§10/§13/§15 | SPEC atualizada | ✓ VERIFIED | Confirmado por leitura direta nesta verificacao |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `main.py` rotas autenticadas | `auth.validar_sessao` | `Depends(usuario_atual)` | ✓ WIRED | Cookie -> hash sha256 -> JOIN `sessoes`/`usuarios` -> `Usuario(**usuario)` |
| `main.py` rotas restritas a admin | `usuario.papel != "admin"` | `Depends(exigir_admin)`, que depende de `usuario_atual` | ✓ WIRED | Composicao confirmada por leitura e pelo teste de inventario (percorre o grafo `.dependant` recursivamente) |
| `gerar_briefings` | `db.salvar(..., dono=usuario.id)` | chamada direta | ✓ WIRED | `main.py:397-399` |
| `historico` | `db.listar(dono=...)` / `db.listar(ver_tudo=True)` | ramificacao por `usuario.papel` | ✓ WIRED | `main.py:458-460` |
| `SPEC §10` (documentacao) | `GUARDAS_ESPERADAS` (`test_smoke.py`) | mesma lista, conferida manualmente nesta rodada | ✓ WIRED | 10 rotas decoradas batem 1:1; a 11a linha (`/static/*`) e mount, coberta por teste separado |
| `index.html` `#admin` (visibilidade) | `GET /api/auth/me` -> `papel` | `admin.hidden = usuarioLogado.papel !== 'admin'` | ✓ WIRED (cliente, cosmetico) — autorizacao real e server-side | `index.html:278`; confirmado que o servidor nao confia nisso (D-17, `exigir_admin` roda independente do cliente) |

### Data-Flow Trace (Level 4)

Nao aplicavel de forma dedicada — a fase nao introduz dashboard com dado agregado novo alem
do historico ja tracado. `historico`/`db.listar` -> `render()` em `index.html` consome a
resposta real de `GET /api/historico` via `fetch`, sem fallback estatico (`index.html:254`,
coluna "dono" so aparece quando `usuarioLogado.papel === 'admin'`).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Suite completa passa (54/54) | `python -m pytest test_smoke.py -q` | `54 passed, 3 warnings in 7.09s` (warnings sao `DeprecationWarning` de `on_event`, ja fora de escopo por decisao explicita — ver CONTEXT.md "herdado da Fase 5: ... depreciacao do on_event") | ✓ PASS |
| §15 done-criterion ao vivo, sem browser, script independente (nao os testes do plano) | script `verify_auth.py` descartavel via `TestClient` | 401 sem sessao (3 rotas admin), 403 com sessao de vendedor (3 rotas admin, inclusive header `X-Papel` forjado), 200 com sessao de admin | ✓ PASS |
| `requirements.txt` intocado desde o esqueleto (L-06) | `git log --oneline -- requirements.txt` | 1 unico commit, `9e2a0d0` (esqueleto original) | ✓ PASS |
| Sem build step / framework novo na UI (L-10) | busca por `package.json`, `node_modules`, `<script src=`/imports de framework | nenhum encontrado | ✓ PASS |
| `.env.example` sem segredo | `git show HEAD:.env.example` | `ADMIN_USERNAME=`/`ADMIN_SENHA=` vazios, `LLM_API_KEY=` vazio, sem valor real | ✓ PASS |
| Debt markers (`TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`) nos arquivos da fase | grep em `app/*.py`, `static/index.html`, `test_smoke.py` | nenhum match real | ✓ PASS |
| Escopo fora-de-escopo (recuperacao de senha, cadastro publico, OAuth/OIDC/SSO) nao implementado | grep case-insensitive em `app/` e `static/index.html` | nenhuma ocorrencia | ✓ PASS |

### Probe Execution

Nao aplicavel — nenhum `scripts/*/tests/probe-*.sh` neste projeto, nenhum plano declara
probes. `SKIPPED (no runnable probes declared or found)`.

### Requirements Coverage

Cobertura de decisoes travadas (D-15..D-19, L-06..L-11) mapeadas por evidencia direta:

| ID | Descricao resumida | Status | Evidencia |
|---|---|---|---|
| L-07 | Autorizacao server-side por requisicao, esconder botao nao conta | ✓ SATISFIED | Ver R-01 done-criterion acima; `exigir_admin` roda independente do estado da UI |
| L-08 | Dois papeis apenas, sem hierarquia | ✓ SATISFIED | `Literal["vendedor","admin"]` em todos os pontos de escrita; ressalva WR-02 (sem `CHECK` no DB) nao contradiz — nenhum caminho de escrita da API produz um terceiro papel |
| L-09 | SQLite continua, sem Postgres | ✓ SATISFIED | `db.py::conectar()` inalterado, `sqlite3.connect` |
| L-10 | UI existente, sem framework, sem build step | ✓ SATISFIED | Ver spot-check acima |
| L-11 | Reaproveita padrao do projeto (`Depends`, `closing(conectar())`, testes em `test_smoke.py`) | ✓ SATISFIED | `auth.py` usa `closing(db.conectar())` identico ao padrao de `db.py`; `usuario_atual`/`exigir_admin` seguem o molde de `_checar_rate_limit` |
| L-06 | Nenhum pacote novo antes da entrega | ✓ SATISFIED | Ver spot-check `requirements.txt` |
| D-15 | Hash scrypt, formato autodescritivo, comparacao constante | ✓ SATISFIED | Ver truth #1 |
| D-16 | Sessao token opaco em SQLite, nao JWT/cookie assinado | ✓ SATISFIED | Ver truth #10 |
| D-17 | Autorizacao por `Depends`, inventario de rotas travado por teste | ✓ SATISFIED | Ver truth #5 |
| D-18 | `owner` aditivo, filtro na leitura, sem migracao destrutiva | ✓ SATISFIED | Ver truths #3, #15, #16 |
| D-19 | Seed do primeiro admin via ambiente, nunca senha default no codigo | ✓ SATISFIED | Ver truth #17 |
| R-01 (aceite adiado da Fase 5) | Rotas sem autenticacao — fase fecha o aceite | ✓ SATISFIED | Ver secao dedicada "R-01 done-criterion" acima |
| R-08 (aceite renovado) | `/health` continua publico | ✓ SATISFIED | `test_rotas_publicas_respondem_sem_cookie` passa; `main.py::health` sem `Depends` de auth |
| R-11 (aceite renovado) | `LLM_BASE_URL` fora do alcance do admin pela UI | ✓ SATISFIED | Ver truth #19 |

Nenhum ID de `06-CONTEXT.md`/`SPEC §15` ficou sem plano ou sem evidencia direta.

### Anti-Patterns Found

Nenhum `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` real nos arquivos tocados pela fase
(grep confirmado nesta rodada). Nenhuma prop/valor vazio hardcoded alimentando renderizacao
dinamica em `index.html` (o painel de historico e a lista de admin consomem `fetch` real).

Os dois achados de `06-REVIEW.md` (nenhum e Critical) sao registrados abaixo, com avaliacao
explicita de bloqueio:

| File | Achado | Severidade | Bloqueia o objetivo da fase (SPEC §15)? |
|---|---|---|---|
| `app/auth.py:173-174` (WR-01) | Timing leak: o ramo "usuario inativo" retorna sem rodar o KDF dummy, entao a resposta e ~5ms contra ~80-100ms dos outros dois casos de 401 identico — um atacante pode inferir, so pela latencia, que uma conta foi desativada, mesmo com o mesmo status/corpo HTTP | ⚠️ Warning | **Nao.** Nao permite que um vendedor alcance uma rota de admin nem quebra a equalizacao entre "usuario inexistente" e "senha errada" (essas duas continuam identicas, e e exatamente isso que `test_login_invalido_nao_distingue_usuario_inexistente_de_senha_errada` trava). E uma lacuna real na garantia mais ampla que o proprio codigo declara ("nunca um motivo diferente para cada caso"), correta a fix sugerido no review, mas nao e o criterio de pronto da fase |
| `app/db.py:48-56` / `main.py` (WR-02) | `usuarios.papel` sem `CHECK` no schema; um valor invalido escrito fora da API (migracao futura, correcao manual de incidente) faz `Usuario(**usuario)` levantar `ValidationError` nao tratada (500) em vez de 401/403 limpo | ⚠️ Warning | **Nao.** Todo caminho de escrita hoje exposto pela API (`CriarUsuarioRequest.papel`, seed do admin) ja fecha a enumeracao no tipo Pydantic antes de qualquer INSERT — o gap so e alcancavel por uma escrita direta no banco fora da API, que nao e uma rota. Nao e uma forma de um vendedor alcancar admin; e um risco de robustez contra dado corrompido, nao de autorizacao |

**Nenhum dos dois Warnings bloqueia o objetivo da fase.** Ambos sao correcoes legitimas e
de baixo custo (poucas linhas), recomendadas para um plano de follow-up rapido, mas nenhum
contradiz a truth #7-#9 nem o done-criterion demonstrado ao vivo nesta verificacao.

### Human Verification Required

### 1. Fluxo visual completo em navegador real (login, admin, escapar de aspas simples)

**Test:** Abrir a UI num navegador real: logar como vendedor, confirmar que a secao de admin
(`#admin`) nunca aparece no DOM renderizado mesmo inspecionando manualmente, colar um link e
ler o cartao de briefing gerado. Depois logar como admin e confirmar visualmente que
listar/criar/ativar/desativar usuarios funciona de ponta a ponta, incluindo o botao de sair
e o painel de historico com a coluna "dono".
**Expected:** Fluxo visual completo funciona sem erro de console do navegador; a area de
admin so aparece para o papel admin; nenhum HTML quebrado ou nao escapado aparece na tela
mesmo com um username contendo aspas simples (ex.: `o'brien`).
**Why human:** Os testes existentes (`test_pagina_inicial_traz_tela_de_login`,
`test_escapar_do_front_cobre_aspas_simples`, `test_front_consome_as_rotas_de_administracao`,
`test_area_de_admin_escondida_nao_e_o_controle_de_acesso`) verificam presenca de marcacao,
strings especificas no HTML servido, e comportamento via `TestClient`/regex sobre o arquivo
— nenhum deles executa JavaScript num motor de renderizacao real. A promessa da SPEC §15
("tela de admin com historico") e um artefato visual; nenhuma checagem automatizada nesta
verificacao (nem nos 54 testes) prova a experiencia renderizada.

### Gaps Summary

**Nenhum gap bloqueante.** As 19 truths derivadas dos seis itens de escopo do
`06-CONTEXT.md` mais os `must_haves` consolidados dos cinco planos estao todas verificadas
com evidencia direta de codigo, 54/54 testes passando, e uma reproducao independente e ao
vivo do criterio de pronto da SPEC §15 (script `TestClient` proprio desta verificacao, nao
os testes do plano) mostrando 401 sem sessao, 403 com sessao de vendedor (inclusive
tentando forjar papel por header) e 200 com sessao de admin nas tres rotas de
`/api/admin/*`. O aceite `R-01`, adiado explicitamente pela Fase 5, esta fechado.

A diferenca entre as 11 linhas de `SPEC §10` e as 10 rotas cobertas pelo teste de
inventario e um gap entendido (o mount `/static/*` nao tem `.dependant` do FastAPI para
percorrer), coberto por um teste companheiro dedicado, e nao representa um buraco real de
autorizacao — o diretorio `static/` so contem `index.html`.

Os dois Warnings do `06-REVIEW.md` (timing leak no ramo de usuario inativo; ausencia de
`CHECK` de banco no papel) sao reais, uteis, e recomendados para correcao rapida — mas
nenhum dos dois permite que um vendedor alcance uma rota de admin, e portanto nenhum dos
dois bloqueia o objetivo desta fase.

O status final e `human_needed`, nao `passed`, porque a promessa "tela de admin com
historico dentro da UI existente" tem um componente inescapavelmente visual que nenhuma
checagem estatica ou `TestClient` prova — fica registrado no item de verificacao humana
acima, exatamente como pedido pelas instrucoes desta rodada ("se algo genuinamente precisa
de um humano num navegador, coloque em `human_verification` em vez de adivinhar").

---

_Verified: 2026-08-27T18:56:45Z_
_Verifier: Claude (gsd-verifier)_
