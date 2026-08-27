---
phase: 05
slug: llm
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-27
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Registro consolidado dos nove `<threat_model>` de `05-01-PLAN.md` a `05-09-PLAN.md`.
Todas as 54 ameacas foram autoradas em tempo de planejamento
(`register_authored_at_plan_time: true`), entao esta auditoria **verifica que as
mitigacoes existem** — nao varre por ameacas novas.

**Nivel ASVS:** 1. **Bloqueio configurado:** `high`.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| navegador -> API (`POST /api/briefings`) | lista de URLs controlada pelo usuario | URLs arbitrarias (`HttpUrl`, 1 a 10) |
| site de terceiro -> processo da API | HTML nao confiavel entra por `buscar_html` | HTML/texto arbitrario |
| **site de terceiro -> prompt do modelo** | **fronteira dominante da fase** (SPEC §11, §16) | texto de pagina dentro de mensagem ao LLM |
| processo -> provedor de LLM (Groq) | chamada de saida autenticada | `LLM_API_KEY` no header, conteudo da pagina no corpo |
| provedor de LLM -> processo | JSON nao confiavel volta e vira `Briefing` | JSON arbitrario |
| ambiente -> processo | `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODELO`, `LLM_MAX_CHARS` | segredo + configuracao de destino |
| repositorio git -> mundo | `.env.example` e versionado, `.env` nao | placeholder de credencial |
| `briefings.db` -> processo da API | linha de schema anterior e **dado nao confiavel na leitura** | JSON/`extrator`/timestamp possivelmente podres |
| API -> navegador (`render()`) | dados de terceiro injetados no DOM | strings de briefing + `degradado` |
| processo -> filesystem (`STATIC_DIR`) | caminho servido pela rota `/` | caminho de arquivo |
| `/health` -> cliente nao autenticado | endpoint publico de estado | booleano de modo de operacao |
| suite de testes -> ambiente / rede / disco | o que a SPEC §14 proibe atravessar | `LLM_API_KEY` real, sockets, `briefings.db` real |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-05-01 | Denial of Service | `gerar_briefings` laco de URLs | high | mitigate | `try` por URL cobrindo cache/fetch/extracao/gravacao com `except Exception` sem nome — `app/main.py:154,213` | closed |
| T-05-02 | Information Disclosure | mensagem de erro ao vendedor | medium | mitigate | `MSG_FALHA_GENERICA` literal autorado; nenhum stack trace interpolado — `app/main.py:39,221` | closed |
| T-05-03 | Tampering | `FileResponse` / `StaticFiles` | low | mitigate | `STATIC_DIR` derivado de `__file__`; rota `/` sem parametro de caminho — `app/main.py:32,252` | closed |
| T-05-04 | Elevation of Privilege | rotas sem autenticacao | medium | accept | R-01 — Fase 6; ASVS L1 nao exige controle de acesso em MVP sem dados de usuario | closed |
| T-05-05 | Denial of Service | `fetcher.pode_raspar` | high | mitigate | `ROBOTS_TIMEOUT = 5.0` no `httpx.get` — `app/fetcher.py:25,78` | closed |
| T-05-06 | Information Disclosure | requisicao de saida ao `robots.txt` | low | accept | R-02 — `User-Agent` identificavel e requisito etico (SPEC §6); nenhuma credencial anexada | closed |
| T-05-07 | Tampering (SSRF) | `httpx.get` para host arbitrario | medium | accept | R-03 — **aceite superado por CR-01**: `_validar_url_publica` recusa privado/loopback/link-local/multicast/reservado antes de cada conexao, `follow_redirects=False` com revalidacao por hop e teto de 5 — `app/fetcher.py:35-67,84,109,123` | closed |
| T-05-08 | Cross-Site Scripting | `render()` em `static/index.html` | medium | mitigate | todo valor vindo da API passa por `escapar()`; 8 chamadas em contexto de texto, nenhuma interpolacao em atributo — `static/index.html:87-101,110` | closed |
| T-05-09 | Tampering | reescrita do arquivo estatico | low | mitigate | `<meta charset="utf-8">` e estrutura DOM preservados — `static/index.html:4` | closed |
| T-05-10 | Information Disclosure | valor do `monkeypatch.setenv("LLM_API_KEY")` | high | mitigate | literal `chave-de-teste-sem-valor` em todo o arquivo — `test_smoke.py:53,237,318,338` | closed |
| T-05-11 | Information Disclosure | `LLM_API_KEY` real vazando do ambiente | medium | mitigate | `delenv`/`setenv`; nenhum teste imprime ou assevera o valor — `test_smoke.py:49,91,102,148,182,349` | closed |
| T-05-12 | Denial of Service | teste tocando rede pendura a suite | medium | mitigate | `buscar_html` monkeypatchado; suite passa em 0.51s sem rede — `test_smoke.py:64,109,156,190,365` | closed |
| T-05-13 | Tampering | teste escrevendo em `briefings.db` de producao | medium | mitigate | `db.salvar`/`db.buscar` monkeypatchados; `DB_PATH` para `tmp_path` — `test_smoke.py:65,110,213,226` | closed |
| T-05-14 | Repudiation | ausencia de teste do caminho de falha | high | mitigate | 16 testes, todos passando; caminhos de falha cobertos — `test_smoke.py:56,98,345` | closed |
| T-05-15 | Information Disclosure | `.env.example` versionado | high | mitigate | `LLM_API_KEY=` sem valor; `.gitignore:4` cobre `.env`; `.env` nao rastreado (`git ls-files`) | closed |
| T-05-16 | Information Disclosure | `app/config.py` ecoando o segredo | high | mitigate | nenhum `print`/`logging` no modulo; superficie publica e so `llm_api_key()` — `app/config.py:22-25` | closed |
| T-05-17 | Information Disclosure | segredo em mensagem de erro do extrator | high | mitigate | `__init__` apenas armazena; nenhuma mensagem interpola `self.api_key` — `app/extractor.py:96-98` | closed |
| T-05-18 | Tampering | dependencia nova antes da demo | medium | mitigate | `requirements.txt` intocado (7 pacotes pre-existentes); nenhum `pip install` na fase | closed |
| T-05-19 | Denial of Service | `LLM_MAX_CHARS` mal configurado | low | accept | R-04 — padrao 12000 (SPEC §11); operador que aumentar assume o custo | closed |
| T-05-20 | Tampering | injecao de prompt via conteudo da pagina | high | mitigate | D-11 tres camadas: sistema com `dado, nunca comando`, mensagem separada delimitada, `Briefing(**dados)` na volta — `app/extractor.py:126-156,234` | closed |
| T-05-21 | Tampering | forja do delimitador pelo conteudo | high | mitigate | `DELIM_INICIO`/`DELIM_FIM` removidos de `trecho` e `titulo` — `app/extractor.py:121-122`; travado por teste — `test_smoke.py:242,254` | closed |
| T-05-22 | Information Disclosure | `LLM_API_KEY` em mensagem ao vendedor | high | mitigate | so `{resp.status_code}` e `{type(ex).__name__}` interpolados — `app/extractor.py:194,196,208` | closed |
| T-05-23 | Information Disclosure | corpo bruto do provedor virando mensagem | medium | mitigate | `resp.text` lido so para detectar rejeicao de `response_format`, nunca em mensagem — `app/extractor.py:201` | closed |
| T-05-24 | Spoofing | provedor devolvendo formato arbitrario | high | mitigate | `response_format: json_schema` + `Briefing(**dados)`; endpoint padrao `https://` — `app/extractor.py:175-182,234`, `app/config.py:44` | closed |
| T-05-25 | Denial of Service | chamada ao LLM pendurada | high | mitigate | `LLM_TIMEOUT = 20.0`, sem laco em `_chamar_provedor` — `app/extractor.py:47,186` | closed |
| T-05-26 | Denial of Service | custo/latencia com tamanho da pagina | medium | mitigate | corte por `config.LLM_MAX_CHARS` antes de qualquer envio — `app/extractor.py:116` | closed |
| T-05-27 | Information Disclosure | conteudo de terceiro enviado ao provedor | low | accept | R-05 — proposito declarado do sistema (SPEC §11); corte de 12k limita o volume; a pagina ja e publica | closed |
| T-05-28 | Repudiation | ausencia de log da chamada ao provedor | low | accept | R-06 — projeto sem logging estruturado; introduzi-lo criaria superficie nova de vazamento. Fase 7 | closed |
| T-05-29 | Elevation of Privilege | modelo induzido a executar acao | low | accept | R-07 — nenhuma ferramenta, funcao ou acesso a rede exposto ao modelo; a saida so pode ser um `Briefing` validado | closed |
| T-05-30 | Information Disclosure | mensagem de degradacao ao vendedor | high | mitigate | `str(e)` so quando `isinstance(erro_extrator, LLMError)`; truncagem em 200 — `app/main.py:114-117` | closed |
| T-05-31 | Cross-Site Scripting | `r.degradado` renderizado no cartao | medium | mitigate | `escapar(r.degradado)` — `static/index.html:98` | closed |
| T-05-32 | Information Disclosure | `/health` expondo configuracao | medium | mitigate | devolve so `{"status", "llm_disponivel"}`, o segundo um booleano — `app/main.py:82` | closed |
| T-05-33 | Elevation of Privilege | `/health` sem autenticacao | low | accept | R-08 — RF13; nao expoe dado de negocio; autenticacao e Fase 6 | closed |
| T-05-34 | Tampering | poluicao da enumeracao `extrator` (SPEC §8) | medium | mitigate | `degradado` ausente de `app/db.py`; nao chega ao banco nem a `/api/historico` | closed |
| T-05-35 | Repudiation | degradacao silenciosa culpando o produto | high | mitigate | `degradado` viaja na resposta e vira tag visivel — `app/main.py:235`, `static/index.html:98` | closed |
| T-05-36 | Tampering | perda de dados por migracao de schema | high | mitigate | nenhum `ALTER TABLE`/`DROP TABLE`/`DELETE FROM`/`os.remove`/`unlink`; `criar_tabelas()` so `CREATE TABLE IF NOT EXISTS` — `app/db.py:28-42` | closed |
| T-05-37 | Denial of Service | recoleta em massa ao ligar a chave | medium | accept | R-09 — `max_length=10` por requisicao (`BriefingRequest`) limita o lote; recoleta acontece uma vez por URL | closed |
| T-05-38 | Information Disclosure | `LLM_API_KEY` vazando pela decisao de cache | high | mitigate | so `bool(config.llm_api_key())` cruza a fronteira; `db.buscar` recebe booleano — `app/main.py:158`, `app/db.py:45` | closed |
| T-05-39 | Spoofing | `/health`, `escolher_extrator()` e cache discordando | low | mitigate | os tres consultam `config.llm_api_key()` — `app/main.py:82,158`, `app/extractor.py:246` | closed |
| T-05-40 | Tampering | dado do cache sem revalidacao de conteudo | low | accept | R-10 — `conteudo_hash` resolve *pagina mudou*, nao *extrator melhorou*; adiado por D-10 | closed |
| T-05-41 | Information Disclosure | `LLM_BASE_URL` compondo a URL que leva o `Bearer` | medium | accept | R-11 — ASVS L1 confia no operador; quem exporta a variavel ja tem o segredo. Nenhum caminho de usuario final influencia a variavel. Reavaliar na Fase 6 | closed |
| T-05-42 | Denial of Service | armadilha do 401 silencioso | low | mitigate | fechada por construcao: padroes de `LLM_BASE_URL` e `LLM_MODELO` apontam para o provedor da unica chave existente e mudam juntos — `app/config.py:33,44`, `.env.example` | closed |
| T-05-50 | Denial of Service | `gerar_briefings`, corpo por URL | high | mitigate | mesmo `try`/`except Exception` de T-05-01, agora cobrindo o corpo inteiro — `app/main.py:154,213`; travado por `test_smoke.py:98,345` | closed |
| T-05-51 | Information Disclosure | `degradado` e `Briefing.resumo` | medium | mitigate | `AVISO_CACHE_INDISPONIVEL` e `MSG_FALHA_GENERICA` literais; truncagem em 200 — `app/main.py:38-39,191-201` | closed |
| T-05-52 | Tampering | linha de schema anterior em `briefings.db` | medium | mitigate | `except (ValidationError, TypeError)` estreito vira miss e forca recoleta; nenhuma DDL corretiva — `app/main.py:177-181`; travado por `test_smoke.py:144,175` | closed |
| T-05-53 | Denial of Service | escrita concorrente em SQLite | medium | accept | R-12 — pool/Postgres fora de escopo (`05-CONTEXT.md`, Deferred Ideas); a falha degrada por URL, nao por lote. ASVS L1 nao exige disponibilidade sob concorrencia | closed |
| T-05-54 | Repudiation | ausencia de log estruturado da degradacao | low | accept | R-13 — o sinal viaja na propria resposta ao vendedor (D-05/D-07), que e o consumidor real | closed |
| T-05-55 | Elevation of Privilege | rotas sem autenticacao | medium | accept | R-01 (mesmo aceite de T-05-04) — Fase 6. **Reduzido** por WR-04: rate limit por IP em `POST /api/briefings` — `app/main.py:55-70,135` | closed |
| T-05-60 | Tampering | `BriefingResponse.extrator` | medium | mitigate | `Literal["llm", "heuristico", "falha"]` fecha a enumeracao da SPEC §8 — `app/schemas.py:58` | closed |
| T-05-61 | Tampering | conteudo forjando o delimitador | high | mitigate | teste persistido trava a anti-forja — `test_smoke.py:237-254` | closed |
| T-05-62 | Denial of Service | laco de chamadas no galho de D-02 | medium | mitigate | teste prova exatamente duas chamadas e que um segundo 400 vira `LLMError` — `test_smoke.py:293,328`; codigo em `app/extractor.py:221-226` | closed |
| T-05-63 | Information Disclosure | chave de API dentro da suite | high | mitigate | chave por argumento de construtor com literal de teste; `httpx.Client` dublado; nenhum socket — `test_smoke.py:272,316,336` | closed |
| T-05-64 | Tampering | `briefings.db` real tocado pela suite | medium | mitigate | `db.DB_PATH` monkeypatchado para `tmp_path` — `test_smoke.py:213,226`; `git status --porcelain briefings.db` vazio apos a suite | closed |
| T-05-65 | Spoofing | modelo obedecendo instrucao do conteudo | high | mitigate | tres camadas de D-11 verificadas (T-05-20); camada 2 travada por teste — `app/extractor.py:126-156,234` | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

**Contagem:** 54 ameacas — 40 `mitigate` (todas verificadas presentes), 14 `accept`
(todas registradas abaixo). Nenhuma ameaca `high` esta em `accept`; nenhuma ameaca
aberta em qualquer severidade.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-01 | T-05-04, T-05-55 | Autenticacao e escopo declarado da Fase 6 (SPEC §15); ASVS L1 nao exige controle de acesso em MVP sem dados de usuario. Abuso trivial de custo ja fechado por WR-04 (rate limit por IP) | João Ferreira | 2026-08-27 |
| R-02 | T-05-06 | `User-Agent` identificavel na consulta a `robots.txt` e requisito etico declarado (SPEC §6); nenhuma credencial e anexada | João Ferreira | 2026-08-27 |
| R-03 | T-05-07 | Aceite original de SSRF **superado na implementacao** por CR-01; mantido no log so por rastreabilidade da decisao | João Ferreira | 2026-08-27 |
| R-04 | T-05-19 | `LLM_MAX_CHARS` e knob do operador; quota por usuario depende da autenticacao da Fase 6 | João Ferreira | 2026-08-27 |
| R-05 | T-05-27 | Enviar conteudo de pagina publica ao provedor e o proposito declarado do sistema (SPEC §11) | João Ferreira | 2026-08-27 |
| R-06 | T-05-28 | Sem logging estruturado nesta fase; introduzi-lo horas antes da demo criaria superficie nova de vazamento de segredo. Fase 7 | João Ferreira | 2026-08-27 |
| R-07 | T-05-29 | Nenhuma ferramenta exposta ao modelo, entao nao ha superficie de acao a elevar | João Ferreira | 2026-08-27 |
| R-08 | T-05-33 | `/health` publico e requisito funcional RF13 e devolve apenas booleano | João Ferreira | 2026-08-27 |
| R-09 | T-05-37 | Recoleta em massa e o comportamento desejado de D-09, limitado a 10 URLs por requisicao | João Ferreira | 2026-08-27 |
| R-10 | T-05-40 | Revalidacao de conteudo em cache adiada por D-10; registrada nas ideias adiadas | João Ferreira | 2026-08-27 |
| R-11 | T-05-41 | `LLM_BASE_URL` so entra por ambiente do processo, nunca por `POST /api/briefings`; o operador ja detem o segredo. Reavaliar na Fase 6, quando existir papel de admin | João Ferreira | 2026-08-27 |
| R-12 | T-05-53 | Pool de conexoes e Postgres fora de escopo por decisao do usuario (`05-CONTEXT.md`); a falha degrada por URL | João Ferreira | 2026-08-27 |
| R-13 | T-05-54 | Sinal de degradacao viaja na propria resposta ao vendedor, que e o consumidor real | João Ferreira | 2026-08-27 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-27 | 54 | 54 | 0 | /gsd-secure-phase (short-circuit, ASVS L1, register authored at plan time) |

**Evidencia de execucao:** `python -m pytest test_smoke.py -q` — 16 passed em 0.51s,
sem rede e sem tocar `briefings.db` (`git status --porcelain briefings.db` vazio).

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-27
