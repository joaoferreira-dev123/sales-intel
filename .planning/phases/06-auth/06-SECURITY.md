---
phase: 06
slug: auth
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (high)
threats_open: 0
asvs_level: 1
created: 2026-08-27
---

# Phase 06 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Register origin: **authored at plan time** — all five phase plans (`06-01` … `06-05`)
carried a `<threat_model>` block. This audit verifies that each declared mitigation is
present in the implementation; it does not scan for new threats.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| navegador → `POST /api/auth/login` | única porta que aceita username e senha | credencial em claro |
| cookie do navegador → `usuario_atual` | token de sessão apresentado a cada requisição | portador de identidade |
| `usuarios` / `sessoes` em `briefings.db` → processo | credencial derivada e sessão em repouso | `senha_hash` (scrypt), `token_hash` (sha256) |
| `usuario_atual` → `exigir_admin` | fronteira de privilégio: vendedor deixa de ser equivalente a admin | papel do usuário |
| processo → resposta HTTP | onde `senha_hash` poderia vazar por descuido de DTO | DTO `Usuario` (4 campos) |
| vendedor A → histórico de vendedor B | fronteira de dados: dois usuários não privilegiados no mesmo banco | linhas de `briefings` |
| cliente → parâmetros de `GET /api/historico` | onde um id de dono forjado entraria, se a rota o aceitasse | `limite` apenas |
| ambiente do processo → tabela de usuários | credencial do primeiro admin cruza aqui, uma vez, na subida | `ADMIN_USERNAME` / `ADMIN_SENHA` |
| administrador → outros usuários | um usuário cria e desativa outros | papel, estado ativo |
| rota → configuração do processo | fronteira declarada **fechada**: nenhuma rota lê ou grava env | — |
| API → DOM | valores de usuários e histórico injetados na página | texto vindo da API |
| site terceiro → rotas POST com cookie | falsificação de requisição entre sites | cookie de sessão |
| repositório git → mundo | `SPEC-sales-intel.md` e `.env.example` são versionados | somente chaves sem valor |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-06-01 | Spoofing | enumeração de username pela resposta do login | medium | mitigate | literal único `MSG_LOGIN_INVALIDO` + 401 único (`app/main.py:210`) | closed |
| T-06-02 | Information Disclosure | enumeração de username por tempo de resposta | medium | mitigate | `_HASH_DUMMY` KDF nos caminhos de usuário inexistente **e** desativado (`app/auth.py:98-102,168-176`) — segundo ramo fechado pelo fix WR-01 (`2aebc3a`) | closed |
| T-06-03 | Information Disclosure | `senha_hash` atravessando a API | high | mitigate | DTO `Usuario` com exatamente 4 campos, nenhum derivado da senha (`app/schemas.py:89-96`) | closed |
| T-06-04 | Spoofing | token de sessão previsível ou forjável | high | mitigate | `secrets.token_urlsafe(32)` do CSPRNG, sem payload (`app/auth.py:195`) | closed |
| T-06-05 | Information Disclosure | token de sessão em repouso | medium | mitigate | banco guarda apenas `sha256` do token (`app/auth.py:196,214,250`) | closed |
| T-06-06 | Elevation of Privilege | `papel` vindo do cliente no login | high | mitigate | `LoginRequest` tem só `username` e `senha` (`app/schemas.py:77-86`) | closed |
| T-06-07 | Spoofing | fixação de sessão | medium | mitigate | nenhuma sessão emitida antes da autenticação; login emite token novo | closed |
| T-06-08 | Information Disclosure | cookie legível por JS ou em claro | high | mitigate | `httponly=True`, `samesite="lax"`, `secure` quando esquema é https (`app/main.py:218-228`) | closed |
| T-06-09 | Tampering | senha recuperável ou KDF fraco | high | mitigate | `hashlib.scrypt` com `n=2**14, r=8, p=1, dklen=32`, salt 16B (`app/auth.py:32-36,55-69`) | closed |
| T-06-10 | Elevation of Privilege | rota de admin alcançada por vendedor via API | critical | mitigate | `exigir_admin` sobre `usuario_atual`, avaliada no servidor (`app/main.py:172`); teste de fechamento SPEC §15 | closed |
| T-06-11 | Information Disclosure | comparação de hash vazando por tempo | medium | mitigate | `hmac.compare_digest` (`app/auth.py:95`) | closed |
| T-06-12 | Denial of Service | senha gigante forçando KDF | medium | mitigate | `max_length=128` no schema, antes do scrypt (`app/schemas.py:84`) | closed |
| T-06-13 | Denial of Service | força bruta no login | high | mitigate | janela de 5 min, 10/IP e 5 falhas/username (`app/main.py:99-140`) | closed |
| T-06-14 | Denial of Service | bloqueio de conta usado como DoS | medium | mitigate | janela deslizante sem estado de conta bloqueada; sucesso limpa o contador | closed |
| T-06-15 | Spoofing | sessão sobrevivendo ao logout | high | mitigate | `encerrar_sessao` remove a linha (`app/auth.py:247`); teste de 401 subsequente | closed |
| T-06-16 | Tampering | injeção de SQL em `auth.py` | high | mitigate | todo `execute` usa placeholders `?`; nenhuma interpolação | closed |
| T-06-17 | Tampering | migração destrutiva nas tabelas novas | medium | mitigate | apenas `CREATE TABLE IF NOT EXISTS` em `criar_tabelas()` | closed |
| T-06-18 | Information Disclosure | credencial de exemplo escrita na SPEC | high | mitigate | `ADMIN_USERNAME=` / `ADMIN_SENHA=` sem valor (`SPEC-sales-intel.md:300-301`) | closed |
| T-06-19 | Repudiation | SPEC e código divergindo sobre o hash | medium | mitigate | divergência argon2→scrypt nomeada citando D-15/L-06 (`SPEC-sales-intel.md:168`) | closed |
| T-06-20 | Repudiation | coluna especificada e nunca implementada | low | mitigate | `conteudo_hash` marcada como não implementada, ref. R-10 (`SPEC-sales-intel.md:155`) | closed |
| T-06-21 | Elevation of Privilege | rota nova nascendo sem guarda | high | mitigate | SPEC §10 é inventário rota+guarda; travado por `test_inventario_de_rotas_declara_guarda_para_cada_rota` | closed |
| T-06-22 | Information Disclosure (IDOR) | `GET /api/historico` | high | mitigate | dono vem de `usuario_atual`; assinatura só tem `limite` (`app/main.py:459-467`) | closed |
| T-06-23 | Information Disclosure | `db.listar` chamada sem recorte | high | mitigate | ramo `else` fail-closed devolve `[]` (`app/db.py:177-182`) | closed |
| T-06-24 | Information Disclosure | linha de briefing sem dono | medium | mitigate | `owner` nulo nunca casa com a cláusula de dono; `test_linha_sem_dono_so_aparece_para_admin` | closed |
| T-06-25 | Tampering | migração destrutiva ao adicionar coluna | high | mitigate | único `ALTER TABLE` guardado por `PRAGMA table_info` (`app/db.py:77-80`); sem `DROP`/`DELETE` | closed |
| T-06-26 | Tampering | troca de dono por recoleta da mesma URL | medium | mitigate | cláusula de conflito de `salvar` não inclui `owner` (`app/db.py:135`) | closed |
| T-06-27 | Elevation of Privilege | `POST /api/briefings` sem sessão drenando LLM | high | mitigate | `usuario_atual` na rota (`app/main.py:344`); limite por IP da Fase 5 permanece | closed |
| T-06-28 | Spoofing | dono gravado a partir de valor do cliente | high | mitigate | `owner` vem de `usuario.id` resolvido pela sessão; nenhum campo do corpo alcança a coluna | closed |
| T-06-29 | Information Disclosure | briefing em cache servido a outro vendedor | low | **accept** | R-14 — cache por URL desde a Fase 3; conteúdo deriva de página pública pedida pelo próprio chamador | closed (accepted) |
| T-06-30 | Tampering | injeção de SQL na cláusula de dono | high | mitigate | placeholders `?` em todos os ramos de `listar` (`app/db.py:146-182`) | closed |
| T-06-31 | Repudiation | teste afrouxado para acomodar a guarda nova | high | mitigate | testes preexistentes mantidos por nome e asserção; suíte 54/54 verde | closed |
| T-06-32 | Spoofing | credencial padrão embutida no código | critical | mitigate | sem valor padrão: `os.getenv(...) or None` (`app/config.py:34,40`); sem as duas variáveis nenhum admin é criado (`app/auth.py:277-278`) | closed |
| T-06-33 | Elevation of Privilege | seed sobrescrevendo ou promovendo usuário existente | high | mitigate | retorna `None` se o username já existe (`app/auth.py:283-284`); `test_semear_admin_inicial_nao_troca_senha_nem_papel_de_usuario_existente` | closed |
| T-06-34 | Spoofing | senha inicial fraca semeada em silêncio | medium | mitigate | mínimo de 12 caracteres, levanta na subida (`app/auth.py:280-281`) | closed |
| T-06-35 | Information Disclosure | credencial de admin vazando pelo repositório | high | mitigate | `.env.example` traz as duas chaves sem valor; `.env` em `.gitignore:4` e não rastreado | closed |
| T-06-36 | Elevation of Privilege | criação de usuário por quem não é admin | critical | mitigate | `POST /api/admin/usuarios` sob `exigir_admin` (`app/main.py:247`); testes de 401 e 403 | closed |
| T-06-37 | Elevation of Privilege | papel arbitrário vindo do corpo | high | mitigate | `Literal["vendedor","admin"]` no schema (`app/schemas.py:110`) + `CHECK` no banco (`app/db.py:52`, fix WR-02) | closed |
| T-06-38 | Information Disclosure | erro do banco vazando em usuário duplicado | medium | mitigate | 409 com literal autorado (`app/main.py:255`) | closed |
| T-06-39 | Elevation of Privilege | sessão viva sobrevivendo à desativação | high | mitigate | `definir_ativo` chama `encerrar_sessoes_do_usuario` (`app/auth.py:317`); `validar_sessao` recusa inativo | closed |
| T-06-40 | Denial of Service | sistema ficando sem admin ativo | medium | mitigate | 400 ao tentar desativar a própria conta (`app/main.py:269`) | closed |
| T-06-41 | Denial of Service | senha longa na criação de usuário | low | mitigate | `max_length=128` no schema (`app/schemas.py:107`) | closed |
| T-06-42 | Elevation of Privilege | rota futura nascendo sem guarda | high | mitigate | igualdade de conjuntos rota↔inventário em `test_inventario_de_rotas_declara_guarda_para_cada_rota` (D-17) | closed |
| T-06-43 | Elevation of Privilege | guarda nova substituindo o limite por IP | medium | mitigate | teste exige `_checar_rate_limit` **e** `usuario_atual` no grafo de `POST /api/briefings` | closed |
| T-06-44 | Information Disclosure | `/docs`, `/redoc`, `/openapi.json` sem sessão | low | **accept** | R-15 — expõem a forma do contrato, nunca dado de negócio; rotas por trás seguem guardadas | closed (accepted) |
| T-06-45 | Elevation of Privilege | `GET /` e `/static/*` públicos | low | **accept** | R-16 — `static/index.html` é a própria tela de login; sem dado de negócio, e L-07 mantém o controle nas rotas de API | closed (accepted) |
| T-06-46 | Cross-Site Scripting | interpolação em atributo na área de admin | high | mitigate | `escapar()` cobre 5 caracteres incl. aspa simples; atributos com aspas duplas (`static/index.html:164`); `test_escapar_do_front_cobre_aspas_simples` | closed |
| T-06-47 | Cross-Site Scripting | valores de usuários e histórico no DOM | medium | mitigate | todo valor da API passa por `escapar()` | closed |
| T-06-48 | Cross-Site Scripting | manipulador de evento embutido na marcação | medium | mitigate | clique tratado por delegação; teste assevera ausência de atributo de evento | closed |
| T-06-49 | Spoofing (CSRF) | rotas POST autenticadas por cookie | medium | mitigate | `SameSite=Lax` (`app/main.py:222`); residual nomeada: GET de navegação carrega cookie mas só devolve JSON ilegível a outra origem. Suficiente para ASVS L1 | closed |
| T-06-50 | Elevation of Privilege | ocultação da área de admin confundida com controle de acesso | high | mitigate | comentário explícito + `test_area_de_admin_escondida_nao_e_o_controle_de_acesso` provando 403 sem navegador (L-07, SPEC §15) | closed |
| T-06-51 | Information Disclosure | senha exposta na tela, histórico ou URL | medium | mitigate | campo mascarado, envio em corpo de POST JSON, campo limpo após envio | closed |
| T-06-52 | Information Disclosure | token de sessão manipulado por JavaScript | high | mitigate | cookie `HttpOnly`; `test_front_nao_desliga_o_envio_de_cookie` proíbe `credentials: 'omit'` | closed |
| T-06-53 | Information Disclosure | sessão expirada deixando tela com dado velho | low | mitigate | 401 no painel devolve o usuário à tela de login | closed |
| T-06-54 | Tampering | regressão de codificação do arquivo (BOM / duplo encode) | medium | mitigate | critério de aceite verifica primeiros bytes e ausência de duplo encode | closed |
| T-06-55 | Information Disclosure | mensagem de erro do framework mostrada ao usuário | low | mitigate | 422 usa frase autorada; demais casos exibem literais autorados via `escapar()` | closed |
| T-05-04 / T-05-55 | Elevation of Privilege | rotas sem autenticação (R-01) | medium | mitigate — **aceite FECHADO** | inventário de todas as rotas com guarda declarada e travado por teste (`06-04` Task 3); o aceite deixa de valer | closed |
| T-05-33 | Elevation of Privilege | `/health` sem autenticação (R-08) | low | **accept — renovado** | RF13 — devolve só `status` e um booleano; escopo travado por `test_rotas_publicas_respondem_sem_cookie` | closed (accepted) |
| T-05-41 | Information Disclosure | `LLM_BASE_URL` compondo a URL que carrega o segredo (R-11) | medium | **accept — renovado com verificação** | nenhuma rota lê ou grava configuração do processo; travado por `test_nenhuma_rota_expoe_configuracao_do_processo` | closed (accepted) |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (high) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-14 | T-06-29 | `briefings` é cache por URL desde a Fase 3 (L-09, SPEC §4). O conteúdo deriva de página pública que o próprio chamador pediu — nenhum dado privado de um vendedor alcança outro. Cache por usuário multiplicaria o custo de LLM, contra o requisito não funcional da SPEC §6. | plano 06-03 | 2026-08-27 |
| R-15 | T-06-44 | `/docs`, `/redoc` e `/openapi.json` expõem a forma do contrato, nunca dado de negócio; todas as rotas por trás continuam guardadas no servidor. ASVS L1 não exige esconder o esquema num protótipo de demonstração. | plano 06-04 | 2026-08-27 |
| R-16 | T-06-45 | `static/index.html` **é** a tela de login — torná-la privada tornaria o login inalcançável. O diretório serve apenas a interface, sem dado de negócio; por L-07 a interface nunca é o controle de acesso. | plano 06-04 | 2026-08-27 |
| R-08 | T-05-33 | `/health` devolve apenas `status` e um booleano, sem dado de negócio (RF13). Renovado nesta fase e agora travado por teste em vez de depender de leitura. | plano 06-04 (renovado) | 2026-08-27 |
| R-11 | T-05-41 | `LLM_BASE_URL` compõe a URL que carrega o segredo. A fronteira operador/usuário passou a existir nesta fase e o aceite se sustenta porque o administrador **não** ganhou poder sobre a configuração: nenhuma rota lê ou grava variável do processo. Promessa convertida em teste em `06-04` Task 3. | plano 06-04 (renovado com verificação) | 2026-08-27 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-27 | 58 | 58 | 0 | /gsd-secure-phase (ASVS L1, grep-depth verification) |

Notes for this run:

- Register origin: authored at plan time across `06-01` … `06-05`; this audit verified declared
  mitigations rather than scanning for new threats.
- Two mitigations were strengthened by the `/gsd-code-review 6 --fix` pass immediately preceding
  this audit: **T-06-02** (commit `2aebc3a` — the deactivated-account branch of `autenticar()` now
  runs the dummy-hash KDF, closing a ~150x timing gap the original mitigation left open on that
  third path) and **T-06-37** (commit `acc947e` — `CHECK (papel IN ('vendedor','admin'))` added at
  the database layer, plus a `ValidationError` → 401 guard).
- The `papel` `CHECK` constraint applies to freshly created tables only; there is no migration for
  an existing `briefings.db`. The `usuario_atual()` guard covers that case at runtime.
- Five Info-level findings from `06-REVIEW.md` remain unfixed by design (outside the default
  `critical_warning` fix scope). None map to an open threat at or above the `high` block threshold.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-27
