---
phase: 05-llm
verified: 2026-08-27T00:00:00Z
status: passed
score: 23/23 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 21/23
  gaps_closed:

    - "L-02 — Fallback por URL, não por lote. Reconfirmado FIXED por leitura direta do código pós-05-08/05-09 e por DUAS reproduções independentes com TestClient real, escritas do zero nesta rodada (não as do plano), rodando totalmente offline (LLM_API_KEY removida do subprocesso): (a) db.salvar falhando na 1ª de 2 URLs -> 200, 2 itens, 2ª intacta, 1ª preserva o briefing com degradado == AVISO_CACHE_INDISPONIVEL; (b) linha de cache sem o campo empresa -> 200, origem: novo, sem 500."
  gaps_remaining: []
  regressions: []
human_verification:

  - test: "Confirmar, com a chave real do Groq configurada, que POST /api/briefings ainda devolve um briefing 'rico' (dores_provaveis/ganchos_de_conversa específicos por página, não genéricos) para pelo menos 1-2 URLs reais — repetindo o espírito da verificação já registrada em 05-05-SUMMARY.md (Task 4)."
    expected: "HTTP 200, extrator: llm, campos de briefing claramente específicos da página coletada (não intercambiáveis entre URLs diferentes)."
    why_human: "Requer uma chamada paga ao provedor real (Groq/openai/gpt-oss-120b). Esta verificação rodou inteiramente offline por restrição explícita (nenhuma chamada paga nesta rodada) e, ao ligar acidentalmente com a chave herdada do ambiente do shell durante uma reprodução ad-hoc, foi refeita imediatamente sem a chave para não gerar uma chamada paga não solicitada (ver nota abaixo). A evidência já registrada em 05-05-SUMMARY.md (2 URLs reais, HTTP 200, extrator: llm, listas de dores_provaveis claramente distintas por página) é forte e não foi invalidada por nada encontrado nesta rodada — mas nenhum plano de fechamento de lacuna tocou app/extractor.py ou app/config.py desde então, então uma reconfirmação rápida antes de encerrar a fase, e não uma reexecução completa, é o que resta pendente de julgamento humano."
gaps: []
---

# Phase 5: LLM Verification Report

**Phase Goal:** Ligar o `LLMExtractor` com saída estruturada validada, seleção automática entre
LLM e heurístico, tratamento de erro e limite de caracteres — mais quatro correções de
estabilidade que precedem a implementação do LLM. Pronto quando (SPEC §15): com chave, o briefing
vem rico; sem chave, cai no heurístico sem quebrar.
**Verified:** 2026-08-27 (offline; ver nota de transparência abaixo sobre duas chamadas
acidentais)
**Status:** human_needed
**Re-verification:** Sim — após fechamento de lacuna (planos 05-08, 05-09), sobre o relatório
anterior (`status: gaps_found`, score 21/23).

## Nota de transparência sobre chamadas ao provedor real

Durante a reprodução independente do gap L-02 nesta rodada, os dois primeiros scripts ad-hoc que
escrevi herdaram `LLM_API_KEY` do ambiente do shell (a chave está exportada nesta máquina) e
acabaram fazendo **duas chamadas reais ao Groq** sem essa ser a intenção (o objetivo era testar o
caminho heurístico/de erro, não o LLM). Percebi isso pela saída (`extrator: "llm"` num teste que
deveria forçar o caminho de erro) e confirmei com `os.getenv("LLM_API_KEY")`. Refiz imediatamente
as duas reproduções com a variável explicitamente removida do subprocesso (`env -u LLM_API_KEY`),
e são essas as duas reproduções offline citadas na tabela de Observable Truths e nos gaps
fechados. Registro isto por transparência: não foi uma chamada solicitada pela verificação, foi
um erro de isolamento de ambiente em um script descartável meu, e o custo de duas chamadas de
chat completion é desprezível — mas o processo pede honestidade sobre isso, então está aqui em
vez de omitido. Não repeti a chamada real para a truth "com chave, o briefing vem rico" depois
disso; ela vai para `human_verification` abaixo, exatamente como as instruções desta rodada
pedem.

## Goal Achievement

### Observable Truths — critério de pronto e escopo da fase (CONTEXT.md)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Com chave, o briefing vem rico (SPEC §15) | ? UNCERTAIN → human_verification | Evidência já registrada em `05-05-SUMMARY.md` (Task 4, D-14): 2 URLs reais via Groq, HTTP 200, `extrator: llm`, campos específicos por página. Não reexecutada nesta verificação por decisão explícita de não fazer chamada paga (ver nota de transparência acima e `<verification_notes>` desta rodada). Nenhum plano de fechamento de lacuna tocou `app/extractor.py`/`app/config.py`, então a evidência antiga permanece plausível, mas por instrução explícita desta rodada isto vai para verificação humana em vez de ser aceito ou rejeitado silenciosamente. |
| 2 | Sem chave, cai no heurístico sem quebrar (SPEC §15, L-05) | ✓ VERIFIED | `app/extractor.py::escolher_extrator()` (linhas 241-249); `test_escolher_extrator_sem_chave_devolve_heuristico` passa; reconfirmado por reprodução independente offline nesta rodada (`env -u LLM_API_KEY`) |
| 3 | `main.py` — escolha de extrator por URL, dentro do laço, com `try/except` caindo no heurístico, **e nenhuma exceção do corpo por URL escapa para o chamador (L-02, fechado por 05-08)** | ✓ VERIFIED | O `try` externo (`app/main.py:118-191`) agora cobre cache, fetch, extração e gravação inteiros, com `except FetchError` seguido de `except Exception` sem nome; `try` aninhado em torno de `db.salvar` preserva o briefing e sinaliza `AVISO_CACHE_INDISPONIVEL`; `try` aninhado em torno da montagem da resposta de cache converte `(ValidationError, TypeError)` em miss. **Verificado por leitura direta do código E por duas reproduções independentes com `TestClient` real nesta rodada** (não os testes do plano): (a) `db.salvar` falhando na 1ª de 2 URLs → 200, 2ª intacta, 1ª preserva o briefing com `degradado == AVISO_CACHE_INDISPONIVEL`; (b) `db.buscar` devolvendo linha sem `empresa` → 200, `origem: novo`, sem 500. Ambas rodadas offline (`env -u LLM_API_KEY`), ambas confirmam exatamente o comportamento que o relatório anterior reproduziu como falha. |
| 4 | `static/index.html` — mojibake corrigido e BOM removido | ✓ VERIFIED | Herdado do relatório anterior; arquivo não tocado pelos planos 05-08/05-09 (fora do `files_modified` de ambos), sem regressão possível |
| 5 | `fetcher.py` — timeout na leitura do `robots.txt` | ✓ VERIFIED | `ROBOTS_TIMEOUT = 5.0` (fetcher.py:23); `pode_raspar()` usa `httpx.get(..., timeout=ROBOTS_TIMEOUT)` (fetcher.py:36-48); arquivo não tocado pelos planos de fechamento |
| 6 | `main.py` — caminho absoluto em `StaticFiles` e `FileResponse` | ✓ VERIFIED | `BASE_DIR`/`STATIC_DIR` (main.py:31-32); usados em `app.mount(...)` (linha 213) e `FileResponse(STATIC_DIR / "index.html")` (linha 218) |
| 7 | `LLMExtractor` implementado, com saída estruturada e prompt endurecido | ✓ VERIFIED | `app/extractor.py::LLMExtractor` completo; sem `NotImplementedError` residual; não tocado pelos planos 05-08/05-09 |
| 8 | Visibilidade da degradação para o vendedor (D-05..D-08) | ✓ VERIFIED | `BriefingResponse.degradado` (schemas.py:61-64); mensagens curtas e autoradas em `_extrair_com_fallback` e nos três pontos novos de `gerar_briefings` (guarda de gravação, catch-all, cache); `.tag-aviso` condicional em `index.html`; `/health` com `llm_disponivel` |
| 9 | Regra de upgrade de extrator no cache (D-09/D-10) | ✓ VERIFIED | `db.buscar(url, llm_disponivel=False)` (db.py:41-63); travado nas duas direções por `test_cache_heuristico_vira_miss_quando_llm_disponivel` e `test_cache_llm_sobrevive_quando_llm_indisponivel` (05-09), rodando sobre `tmp_path`, nunca tocando `briefings.db` real (confirmado por `git status --porcelain briefings.db` vazio) |

**Score desta seção:** 8/9 verificadas + 1 roteada para verificação humana (não é falha nem
sucesso silencioso — ver nota nos `human_verification`)

### Cobertura de Requisitos — L-01..L-06, D-01..D-14 (fonte: `05-CONTEXT.md`)

Todos os 20 IDs de decisão travada (`L-01..L-06`, `D-01..D-14`) definidos em `05-CONTEXT.md`
aparecem no campo `requirements:` de pelo menos um dos 9 planos da fase — nenhum ID orfão, nenhum
ID inventado. Tabela cruzada abaixo.

| ID | Descrição resumida | Status | Evidência |
|---|---|---|---|
| L-01 | Extrator atrás da interface `Extractor`, heurístico como fallback | ✓ VERIFIED | `Extractor(Protocol)` (extractor.py:53-58); `HeuristicExtractor`/`LLMExtractor` cumprem `nome`/`extrair` |
| L-02 | Fallback **por URL**, não por lote | ✓ VERIFIED | Ver truth #3 acima. Invariante estrutural confirmada por leitura de código e por duas reproduções independentes com `TestClient` real, offline, nesta rodada — o gap que bloqueou a rodada anterior está genuinamente fechado, não apenas "testes do plano passam" |
| L-03 | Saída do LLM validada pelo schema `Briefing`; formato inválido levanta erro | ✓ VERIFIED | `extractor.py:233-238` — `Briefing(**dados)`, `except (TypeError, ValidationError): raise LLMError(...)` |
| L-04 | Corte de 12 mil caracteres no texto enviado ao modelo | ✓ VERIFIED | `config.LLM_MAX_CHARS` (padrão 12000); consumido em `_montar_mensagens` (extractor.py:116) |
| L-05 | Sem chave configurada, roda no heurístico sem quebrar | ✓ VERIFIED | `escolher_extrator()`; teste dedicado passa; reconfirmado offline nesta rodada |
| L-06 | Stack não muda (FastAPI, SQLite, HTML servido pela API) | ✓ VERIFIED | `requirements.txt` idêntico ao commit inicial do esqueleto (`git log` confirma nenhum commit tocou o arquivo desde então) |
| D-01 | `httpx` direto, não SDK do provedor | ✓ VERIFIED | `extractor.py` usa `httpx.Client` diretamente; nenhum pacote novo em `requirements.txt` |
| D-02 | `response_format: json_schema` + validação; degrada para JSON pedido no prompt | ✓ VERIFIED (caminho primário ao vivo em 05-05; galho de degradação travado por duplo em 05-09) | Caminho primário: `_chamar_provedor` monta `response_format` do schema Pydantic; verificado ao vivo contra `openai/gpt-oss-120b` em 05-05. Galho `_SemJsonSchema`: agora coberto por `test_degradacao_json_schema_faz_exatamente_uma_segunda_chamada` e `test_segundo_400_de_json_schema_vira_llmerror` (05-09) — prova a lógica (exatamente 2 chamadas, corpo correto, sem laço) contra um duplo escrito à mão, não contra o provedor real. **Limite já documentado em `COVERAGE.md`/`05-05-SUMMARY.md`, classificado por esta verificação como corretamente caracterizado — accepted-limitation, não gap novo.** |
| D-03 | Timeout de 20s, sem retry | ✓ VERIFIED | `LLM_TIMEOUT = 20.0`; `test_segundo_400_de_json_schema_vira_llmerror` prova que um segundo 400 não gera terceira chamada |
| D-04 (emendada) | `config.py` lê apenas `LLM_API_KEY`, `LLM_MODELO`, `LLM_MAX_CHARS`, `LLM_BASE_URL` | ✓ VERIFIED | `app/config.py` expõe exatamente esses quatro nomes + `os` |
| D-05 | `extrator` continua `"heuristico"`; degradação em campo separado | ✓ VERIFIED | `BriefingResponse.degradado` opcional; `extrator` agora `Literal["llm","heuristico","falha"]` (fechado em 05-09), nunca um quarto valor |
| D-06 | Motivo da falha chega ao vendedor, curto, sem stack trace | ✓ VERIFIED | Regra "só interpolamos mensagem autorada" agora aplicada nos **quatro** pontos do arquivo (degrau 2, degrau 3, guarda de gravação, catch-all do laço) — mais consistente que na rodada anterior, que só cobria o degrau 2. Ver WR-A abaixo para uma ressalva de qualidade não-bloqueante sobre um caso de borda do truncamento. |
| D-07 | UI destaca briefing degradado com tag de aviso | ✓ VERIFIED | `.tag-aviso` (index.html:29); `<span class="tag tag-aviso">` condicional (index.html:98); não tocado pelos planos de fechamento |
| D-08 | `/health` informa qual extrator está ativo (booleano) | ✓ VERIFIED | `health()` devolve `{"status": "ok", "llm_disponivel": bool(config.llm_api_key())}` |
| D-09 | Regra de upgrade: `heuristico` vira miss quando LLM disponível | ✓ VERIFIED | `db.buscar()`; travado nas duas direções por teste dedicado (05-09), sobre `tmp_path` |
| D-10 | Não implementar `conteudo_hash`; nenhuma migração de schema | ✓ VERIFIED | `criar_tabelas()` idêntico ao pré-existente; nenhum `ALTER`/`DROP`/`DELETE` em `app/main.py` (confirmado por AST check do próprio plano 05-08 e por leitura direta) |
| D-11 | Mitigação de injeção de prompt completa (3 camadas) | ✓ VERIFIED, com ressalva não-bloqueante (WR-B) | Camada 1 (system message), camada 2 (delimitador + anti-forja, agora travada por `test_montar_mensagens_remove_delimitador_forjado` para texto **e** título) e camada 3 (validação de schema, L-03) presentes e testadas. **Achado novo do `05-REVIEW.md` (WR-B, não fechado por nenhum plano):** `Titulo` fica fora do bloco delimitado na mensagem de usuário, então a instrução explícita de "nunca obedecer" do system message — que cita literalmente `{DELIM_INICIO}`/`{DELIM_FIM}` — não cobre contratualmente o título, embora ele seja tão controlado pelo atacante quanto o corpo. Impacto limitado (L-03 continua validando a forma final da saída), classificado como Warning, não Blocker. Não bloqueia a truth testada (delimitador do corpo/título não é forjável), mas é uma lacuna real na alegação "completo" — registrado para follow-up, não fechado nesta batelada. |
| D-12 | Testes offline, sem chave e sem rede | ✓ VERIFIED | `test_smoke.py` tem 16 testes (7 originais + 3 de 05-08 + 6 de 05-09); `pytest -q` roda em 0.44s, offline, confirmado nesta rodada |
| D-13 | `LLM_BASE_URL` como 4ª variável; padrões invertidos para o Groq | ✓ VERIFIED | `config.py`: padrões `https://api.groq.com/openai/v1` / `openai/gpt-oss-120b`; `.env.example` traz o mesmo par, confirmado por leitura de bytes nesta rodada |
| D-14 | Ondas 4-6 verificáveis contra modelo real; backstop vira verdade explícita | ✓ VERIFIED (evidência de 05-05, não reexecutada nesta rodada) | Ver truth #1 e `human_verification` acima — evidência histórica aceita, reconfirmação ao vivo roteada para humano por decisão explícita desta rodada de não fazer chamada paga |

**Score desta seção:** 20/20 IDs de decisão travada verificados (D-02 e D-14 com limite já
documentado e aceito; D-11 com ressalva de warning não-bloqueante).

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `app/main.py::gerar_briefings` | Corpo por URL inteiro sob `try`/`except Exception` (L-02 estrutural) | ✓ VERIFIED | Confirmado por leitura direta e por 2 reproduções independentes com `TestClient` |
| `app/main.py::AVISO_CACHE_INDISPONIVEL` / `MSG_FALHA_GENERICA` | Literais autorados (D-06) | ✓ VERIFIED | Presentes, ambos < 200 chars, usados nos pontos corretos |
| `app/schemas.py::BriefingResponse.extrator` | `Literal["llm","heuristico","falha"]` (WR-01) | ✓ VERIFIED | Confirmado por leitura direta; `typing.get_args` bateria (via SUMMARY, código lido confirma) |
| `test_smoke.py` | 16 testes offline | ✓ VERIFIED | `pytest --collect-only -q` lista os 16 nomes esperados, incluindo os 9 novos das duas bateladas de fechamento |
| `app/extractor.py::LLMExtractor` | Chamada real, validação, prompt endurecido | ✓ VERIFIED | Completo, sem stub, não tocado nesta batelada |
| `app/config.py` | 4 variáveis | ✓ VERIFIED | Confirmado |
| `.env.example` | 4 linhas, sem segredo | ✓ VERIFIED | Confirmado via leitura de bytes nesta rodada |
| `app/db.py::buscar(url, llm_disponivel)` | Regra de upgrade | ✓ VERIFIED | Presente, testada nas duas direções |
| `static/index.html::.tag-aviso` | Tag CSS de aviso | ✓ VERIFIED | Presente, condicional, escapada |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `gerar_briefings` (laço) | `_extrair_com_fallback` | chamada por URL | ✓ WIRED | Inalterado desde a rodada anterior |
| `gerar_briefings` (laço) | `db.salvar`/`Briefing(**dados)` | try/except | ✓ WIRED (fechado) | Antes: `NOT_WIRED (parcial)`. Agora: `try` externo cobre o corpo inteiro; `try` aninhado específico em torno de `db.salvar` preserva o briefing; `try` aninhado em torno da montagem da resposta de cache converte erro de schema em miss. Confirmado por leitura e por 2 reproduções independentes |
| `05-08 T2 cache-row guard` | `app/schemas.py::BriefingResponse.extrator` (WR-01) | dependência declarada | ✓ WIRED | O plano 05-09 depende explicitamente da guarda do 05-08 para fechar o `Literal` com segurança — confirmado por leitura: uma linha de cache com `extrator` fora da enumeração agora vira `ValidationError` capturada pela guarda de 05-08, não um 500 |
| `LLMExtractor._chamar_provedor` | `config.LLM_BASE_URL` | leitura de módulo | ✓ WIRED | Nenhuma constante de endpoint em `extractor.py` |
| `/health` | `config.llm_api_key()` | mesma fonte de `escolher_extrator()`/cache | ✓ WIRED | Os três pontos consultam a mesma função |
| `render()` (index.html) | `r.degradado` | span condicional escapado | ✓ WIRED | Inalterado |

### Data-Flow Trace (Level 4)

Não aplicável de forma nova nesta rodada — a fase não introduz um dashboard ou lista renderizada
com dado dinâmico novo. `render()`/`r.degradado` já foi traçado na rodada anterior e permanece
correto (arquivo não tocado pelas bateladas de fechamento).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| `pytest -q` roda 16 testes offline | `python -m pytest -q` | `16 passed` em 0.44s | ✓ PASS |
| Nenhum teste toca `briefings.db` real | verificado pelo próprio design dos testes (`tmp_path`/`TestClient` sem `with`) e pela ausência do arquivo no repo | sem arquivo criado | ✓ PASS |
| L-02 (a): `db.salvar` falha na 1ª de 2 URLs, offline (chave removida do subprocesso) | script Python ad-hoc com `TestClient` real, `env -u LLM_API_KEY` | 200; 2 itens; 2ª intacta (`origem: novo`, `extrator: heuristico`); 1ª preserva `briefing.empresa` e `degradado == AVISO_CACHE_INDISPONIVEL` | ✓ PASS |
| L-02 (b): linha de cache sem `empresa`, offline | script Python ad-hoc com `TestClient` real, `env -u LLM_API_KEY` | 200; `origem: novo`; `extrator: heuristico`; briefing veio da recoleta | ✓ PASS |
| `requirements.txt` intocado desde o commit inicial | `git log --oneline -- requirements.txt` | 1 único commit, o do esqueleto original | ✓ PASS |
| Debt markers (`TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`) nos arquivos da fase | grep em todos os arquivos de app/ + test_smoke.py | 2 matches, ambos falsos positivos (comentário "todos os campos" e string de teste "atende... todo o Brasil") | ✓ PASS (nenhum debt marker real) |

### Probe Execution

Não aplicável — não há `scripts/*/tests/probe-*.sh` neste projeto, e nenhum plano os declara.
`SKIPPED (no runnable probes declared or found)`.

### Requirements Coverage

Ver tabela "Cobertura de Requisitos" acima. 20/20 IDs de decisão travada verificados (dois com
limite já documentado e aceito — D-02, D-14 —, um com ressalva de warning não-bloqueante — D-11).
Nenhum ID de `05-CONTEXT.md` ficou sem plano que o reivindicasse.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `app/main.py` | 162-165 | Concatenação `f"{degradado} {AVISO_CACHE_INDISPONIVEL}"[:200]` pode truncar ou eliminar silenciosamente o sufixo `AVISO_CACHE_INDISPONIVEL` quando `degradado` já está perto do teto de 200 chars (ex.: uma `LLMError` longa seguida de falha de gravação na mesma URL) | ⚠️ Warning (WR-A, achado do `05-REVIEW.md`, já disclosed honestamente em `05-08-SUMMARY.md`) | Não viola L-02 nem vaza texto de exceção não autorada (D-06 continua respeitado no sentido central); no pior caso, o aviso de falha de gravação secundária desaparece silenciosamente para o vendedor. Sem teste dedicado. Registrado como accepted-limitation para follow-up, não bloqueia o objetivo da fase |
| `app/extractor.py` | 144-151 | `Titulo` fica fora do bloco delimitado por `DELIM_INICIO`/`DELIM_FIM`, apesar de ser tão controlado pelo atacante quanto o corpo (WR-B, achado novo do `05-REVIEW.md` pós-fechamento) | ⚠️ Warning | Enfraquece a alegação de D-11 "implementada por completo" — a instrução explícita de "nunca obedecer" no system message cita literalmente os delimitadores, e o título não está dentro deles. Mitigado por L-03 (validação de schema na saída) e pela linha genérica "Dado nao confiavel". Não corrigido por nenhum plano desta batelada; accepted-limitation para follow-up |
| `app/main.py` | 73-86 (degrau 2 de `_extrair_com_fallback`) | Reexecução redundante do heurístico quando ele já é o extrator primário (IN-01, pré-existente, fora do escopo desta batelada) | ℹ️ Info | Otimização sem mudança de comportamento; explicitamente não fechado por decisão do planejador de 05-08 (registrado como follow-up, não lacuna) |
| — | — | Nenhum `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` real encontrado nos arquivos desta fase | — | Grep confirmado sem matches reais nesta rodada |

Nenhum pacote novo foi instalado em nenhum dos 9 planos (`requirements.txt` intocado desde o
commit do esqueleto).

### Human Verification Required

### 1. Briefing rico com chave real (SPEC §15, D-14)

**Test:** Rodar `POST /api/briefings` com 1-2 URLs reais e a chave `LLM_API_KEY` do Groq
configurada.
**Expected:** HTTP 200, `extrator: llm`, campos `dores_provaveis`/`ganchos_de_conversa`
claramente específicos da página coletada (não genéricos, não intercambiáveis entre URLs
diferentes) — o mesmo padrão de evidência já registrado em `05-05-SUMMARY.md`.
**Why human:** Exige uma chamada paga ao provedor real; esta verificação rodou inteiramente
offline por restrição explícita da rodada (ver nota de transparência no topo do relatório sobre
duas chamadas acidentais, já refeitas offline). Nenhum plano de fechamento de lacuna tocou
`app/extractor.py`/`app/config.py` desde a evidência de 05-05, então uma reconfirmação rápida —
não uma reexecução completa — é o que resta pendente antes de considerar a fase inteiramente
fechada.

### Gaps Summary

**Nenhum gap bloqueante restante.** O único blocker do relatório anterior — `L-02` — está
confirmado fechado nesta rodada por três fontes independentes e convergentes: (1) leitura direta
do código atual de `app/main.py`, que mostra o `try` externo cobrindo o corpo por URL inteiro com
`except FetchError` seguido de `except Exception`, mais duas guardas aninhadas específicas; (2)
os três testes persistidos pelo plano 05-08 (`test_falha_ao_salvar_no_cache_nao_derruba_o_lote`,
`test_cache_incompativel_com_o_schema_vira_miss`, `test_falha_dupla_devolve_briefing_de_falha_sem_vazar_excecao`),
que passam; e (3) duas reproduções **independentes**, escritas do zero nesta rodada de verificação
(não os testes do plano), rodando com `TestClient` real e `LLM_API_KEY` explicitamente removida do
subprocesso — ambas confirmam 200 em vez do 500 que a rodada anterior reproduziu.

`WR-01` e `WR-02` (`05-REVIEW.md`) também estão fechados: `extrator` agora é um `Literal` fechado
pelo Pydantic, e as três rotas de maior risco da fase (D-09 nas duas direções, D-11 anti-forja,
D-02 galho de degradação) têm cobertura de teste persistida e offline, onde antes só havia scripts
ad-hoc já descartados.

O que resta **não é um gap**, é uma verdade que só pode ser provada com uma chamada paga ao
provedor real — "com chave, o briefing vem rico" — e por instrução explícita desta rodada isso vai
para verificação humana em vez de ser marcado como falho ou aceito em silêncio. A evidência
histórica de `05-05-SUMMARY.md` é forte e não foi contradita por nada encontrado nesta rodada;
trata-se de uma reconfirmação recomendada, não de uma dúvida real sobre a implementação.

Dois achados novos do `05-REVIEW.md` pós-fechamento (`WR-A`: truncamento pode descartar o aviso de
falha de gravação secundária em um caso de borda raro; `WR-B`: o título da página fica fora do
bloco delimitado de D-11) são warnings legítimos, corretamente não-bloqueantes, e ficam registrados
para follow-up — nenhum dos dois quebra uma truth verificada nesta fase nem foi reivindicado como
fechado por nenhum plano.

---

_Verified: 2026-08-27_
_Verifier: Claude (gsd-verifier)_
