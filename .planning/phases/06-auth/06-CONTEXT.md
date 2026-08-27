# Phase 6: Auth — Context

**Gathered:** 2026-08-27
**Status:** Ready for planning

> **Nota de processo:** este projeto continua sem `.planning/ROADMAP.md` — o diretório
> `.planning/` tem apenas `codebase/`, `config.json` e `phases/`. `SPEC-sales-intel.md`
> §15 segue sendo o roadmap efetivo, como na Fase 5. O diretório `06-auth/` foi criado
> manualmente para que o resolver de fase do GSD encontre a fase (ele resolve por
> diretório, não por ROADMAP). Escopo desta fase ditado diretamente pelo usuário em
> 2026-08-27, sob restrição de prazo: **entrega até amanhã de manhã**.

<domain>
## Phase Boundary

Autenticação com usuário e senha, dois papéis, e proteção das rotas da API **no
servidor**. É o Bônus 2 da SPEC.

**Pronto quando** (SPEC §15): vendedor não acessa rota de admin nem chamando a API
direto.

**Entra nesta fase:**
1. Login com usuário e senha, senha guardada com hash forte
2. Dois papéis: `vendedor` e `admin`
3. Vendedor gera briefing e vê o **próprio** histórico
4. Admin vê tudo e gerencia usuários
5. Toda rota da API valida papel no servidor a cada requisição
6. Tela de login e área de admin dentro da UI existente

**Fora de escopo, por decisão explícita do usuário — não implementar e não discutir:**
recuperação de senha, cadastro público, integração com provedor externo de identidade.
Também segue fora, herdado da Fase 5: Postgres, React, depreciação do `on_event`.

</domain>

<spec_lock>
## Requirements (locked via SPEC-sales-intel.md)

Requisitos travados em `SPEC-sales-intel.md`. Downstream agents **MUST** ler a SPEC
antes de planejar ou implementar. Seções que governam esta fase:

- **§8** — tabela `usuarios`: `id`, `username` (único), `senha_hash`, `papel`
  (`vendedor` | `admin`), `ativo`. **Ver D-15 para a divergência de algoritmo de hash.**
- **§10** — rotas do bônus 2: `POST /api/auth/login`, `GET /api/auth/me`,
  `GET /api/admin/usuarios`.
- **§15** — definição e critério de pronto da Fase 6.
- **§6** — requisitos não funcionais.
- **§17** — definição de pronto.

</spec_lock>

<locked_decisions>
## Decisões travadas pelo usuário — NÃO reabrir

Trazidas já decididas em 2026-08-27. Downstream agents tratam como fixas:

- **L-07:** Autorização é **server-side por requisição**. Esconder botão na UI não é
  controle de acesso e não conta como mitigação. O critério de pronto da SPEC §15 é
  explícito: o vendedor não pode alcançar rota de admin nem chamando a API direto.
- **L-08:** Dois papéis apenas: `vendedor` e `admin`. Sem hierarquia, sem permissões
  granulares, sem papel extra "por via das dúvidas".
- **L-09:** SQLite continua. Sem migração para Postgres nesta fase.
- **L-10:** UI existente (`static/index.html`, vanilla JS). Sem trocar por framework,
  sem build step, sem dependência de front novo.
- **L-11:** Reaproveitar o padrão do resto do projeto — mesma estrutura de módulo,
  mesmo estilo de erro, mesmos testes em `test_smoke.py`, mesmas convenções de
  `.planning/codebase/CONVENTIONS.md`.
- **L-06 (herdada da Fase 5, reafirmada):** não instalar pacote novo antes da entrega.
  Ver D-15.

</locked_decisions>

<decisions>
## Implementation Decisions

- **D-15 — Hash de senha: `hashlib.scrypt` da stdlib, não argon2.**
  **Divergência consciente da SPEC §8**, que escreve `senha_hash | texto (argon2)`.
  Decidida pelo usuário em 2026-08-27 quando o conflito foi apresentado.
  *Motivo:* `argon2-cffi` é pacote novo **com extensão C compilada**, e L-06/D-01
  proíbe dependência nova antes da entrega — regra citada no gate de
  package-legitimacy dos nove planos da Fase 5. `hashlib.scrypt` é KDF memory-hard,
  está na stdlib, e não tem risco de falhar o build em máquina limpa na Fase 7
  (Docker/README). Verificado disponível neste ambiente.
  *Forma de armazenamento:* string autodescritiva com os parâmetros embutidos, para
  que um aumento futuro de custo não invalide os hashes já gravados:
  `scrypt$<n>$<r>$<p>$<salt_b64>$<chave_b64>`. Parâmetros iniciais `n=2**14, r=8,
  p=1, dklen=32`, salt de 16 bytes de `secrets.token_bytes`.
  *Comparação:* `hmac.compare_digest`, nunca `==`.
  *Ação:* atualizar `SPEC-sales-intel.md` §8 para refletir a decisão, em vez de
  deixar SPEC e código divergentes silenciosamente.

- **D-16 — Sessão: token opaco em tabela SQLite, não JWT nem cookie assinado.**
  Nem `jwt` nem `itsdangerous` estão instalados (verificado), e L-06 proíbe instalar.
  As alternativas sem pacote novo seriam assinar um cookie à mão com `hmac` — cripto
  escrita à mão na véspera da entrega — ou guardar sessão no banco. A segunda é
  estritamente mais simples e casa com L-09: o token é só `secrets.token_urlsafe(32)`,
  opaco, sem payload para forjar. Revogação vira `DELETE`, que é o que "admin
  desativa usuário" precisa. Cookie `HttpOnly`, `SameSite=Lax`, `Secure` condicionado
  a HTTPS (a demo roda em `http://localhost`).

- **D-17 — Autorização por dependência do FastAPI, não por checagem espalhada.**
  Mesmo padrão já usado por `_checar_rate_limit` (`app/main.py:55-70`, via
  `Depends`), o que satisfaz L-11. Duas dependências: `usuario_atual` (401 se não
  autenticado) e `exigir_admin` (403 se `papel != "admin"`). Uma rota sem dependência
  declarada é rota desprotegida — o plano precisa de critério de aceite que enumere
  **todas** as rotas e o guarda de cada uma, senão a próxima rota adicionada nasce
  aberta.

- **D-18 — `briefings` ganha dono; a leitura é que filtra.**
  Vendedor vê o próprio histórico, admin vê tudo. Mesma política de D-10 da Fase 5:
  a regra vive na leitura, não numa migração destrutiva. Linha antiga sem dono é dado
  velho — precisa de decisão explícita no plano sobre o que o vendedor vê (proposta:
  linha sem dono é visível só para admin, e o plano trava isso com teste).
  **Sem `ALTER TABLE` destrutivo, sem `DELETE`, sem `DROP`** — herdado de D-10/T-05-36.

- **D-19 — Semear o primeiro admin sem cadastro público.**
  Cadastro público está fora de escopo, então precisa existir um caminho de bootstrap.
  Proposta a decidir no plano: comando/função de seed lendo de variável de ambiente,
  no padrão de `app/config.py`. **Nunca** com senha default embutida no código.

</decisions>

<threat_seeds>
## Sementes de threat model — Fase 5 deixou dívida nomeada para cá

Quatro ameaças da Fase 5 foram aceitas com "reavaliar na Fase 6". O threat model
desta fase **deve** retomá-las, não recriá-las do zero:

- **T-05-04 / T-05-55** (`R-01`) — rotas sem autenticação, aceito porque autenticação
  era escopo declarado desta fase. **Esta fase fecha o aceite.**
- **T-05-33** (`R-08`) — `/health` sem autenticação. Decidir explicitamente se
  continua público (é requisito funcional RF13 e só devolve booleano) ou passa a
  exigir sessão. Recomendação: continua público, com o aceite renovado.
- **T-05-41** (`R-11`) — `LLM_BASE_URL` operador-controlada. O aceite dizia
  literalmente *"reavaliar na Fase 6, quando existir papel de admin e a fronteira
  operador/usuário deixar de ser a mesma pessoa"*. **Essa fronteira passa a existir
  agora** — se o admin puder editar configuração pela UI, o aceite cai e vira ameaça
  ativa. Se configuração continuar só por variável de ambiente do processo, o aceite
  se mantém. Decidir no plano.

Ameaças novas óbvias a cobrir (não exaustivo — o planner faz o STRIDE completo):
enumeração de usuário no login, força bruta no login (há rate limit por IP em
`/api/briefings`, mas não em `/api/auth/login`), fixação de sessão, timing attack na
comparação de hash, IDOR no histórico por `id` de outro vendedor, escalada por
`papel` vindo do cliente em vez do servidor, e XSS na nova área de admin (o
`escapar()` de `static/index.html:110` cobre `&<>"` mas **não** `'` — a área de admin
não pode interpolar em atributo com aspas simples).

</threat_seeds>

<canonical_refs>
## Canonical References

- `SPEC-sales-intel.md` §8, §10, §15, §17
- `.planning/phases/05-llm/05-SECURITY.md` — aceites R-01, R-08, R-11 a reavaliar
- `.planning/codebase/CONVENTIONS.md` — estilo travado por L-11
- `.planning/codebase/ARCHITECTURE.md`
- `app/main.py:55-70,132-136` — padrão `Depends` a reaproveitar (D-17)
- `app/db.py` — padrão `closing(conectar())`, SQL parametrizado, `CREATE TABLE IF NOT EXISTS`
- `app/config.py` — padrão de leitura de ambiente (D-19)
- `static/index.html:110` — `escapar()`, cobre `&<>"` e não `'`

</canonical_refs>

<code_context>
## Existing Code Insights

- **`Depends` já em uso.** `_checar_rate_limit` (`app/main.py:55-70`) é dependência
  de rota declarada em `dependencies=[...]`. D-17 segue exatamente esse molde.
- **Rotas hoje existentes, todas abertas:** `GET /health`, `POST /api/briefings`,
  `GET /api/historico`, `GET /`, `/static/*`. O plano precisa decidir o guarda de
  cada uma, incluindo as duas últimas.
- **`GET /api/historico` (`app/main.py:243-246`) chama `db.listar(limite)`**, que faz
  `SELECT` sem cláusula de dono. É o ponto exato onde D-18 incide.
- **`db.py` já tem o padrão certo:** `with closing(conectar()) as conn, conn:`,
  SQL sempre parametrizado, `CREATE TABLE IF NOT EXISTS`. Tabelas novas seguem isso.
- **Testes:** `test_smoke.py`, 16 testes, offline, `DB_PATH` via `monkeypatch` para
  `tmp_path`. Testes novos herdam essa disciplina (T-05-64).
- **`escapar()` não cobre `'`** — irrelevante hoje porque nada é interpolado dentro de
  atributo, mas a área de admin é código HTML novo e pode reintroduzir o risco.

</code_context>

<open_questions>
## Perguntas em aberto — para o planner resolver ou escalar

1. **Linha de `briefings` sem dono** (pré-Fase 6): visível só para admin, ou atribuída
   ao primeiro admin no seed? (D-18)
2. **`/health` continua público?** Recomendação: sim, aceite R-08 renovado. (T-05-33)
3. **Admin edita configuração pela UI?** Se sim, o aceite R-11 de `LLM_BASE_URL` cai.
   Recomendação: não — configuração continua só por ambiente, aceite mantido. (T-05-41)
4. **Rate limit no login.** Reaproveitar `_checar_rate_limit` com janela/limite
   próprios, ou limite por `username` além de por IP?
5. **Bootstrap do primeiro admin:** variável de ambiente lida no startup, ou script
   separado? (D-19)

</open_questions>

<deferred>
## Deferred Ideas

- Recuperação de senha — fora de escopo, decisão do usuário
- Cadastro público — fora de escopo, decisão do usuário
- Provedor externo de identidade (OAuth/OIDC/SSO) — fora de escopo, decisão do usuário
- Rotação de parâmetros de `scrypt` / re-hash no login — o formato de D-15 já permite,
  a implementação fica para depois da entrega
- Logging estruturado de eventos de auth — herdado de R-06 (Fase 7)
- Postgres, pool de conexões — herdado de R-12

</deferred>
