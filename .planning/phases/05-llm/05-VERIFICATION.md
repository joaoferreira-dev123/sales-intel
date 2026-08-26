---
phase: 05-llm
verified: 2026-08-26T00:00:00Z
status: gaps_found
score: 21/23 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "L-02 — Fallback por URL, não por lote. Um link ruim não contamina os outros."
    status: failed
    reason: >
      O laço de gerar_briefings (app/main.py) só captura FetchError. Duas rotas de exceção
      escapam desse guarda e derrubam o lote inteiro em vez de degradar só a URL afetada:
      (1) db.salvar(...) na linha 125 — uma falha de escrita (ex.: "database is locked" em
      SQLite sob concorrência) propaga sem tratamento; (2) Briefing(**dados) na linha 110,
      no caminho de leitura do cache — uma linha antiga em briefings.db que não bate mais
      com o schema atual de Briefing levanta ValidationError sem tratamento. Reproduzido
      neste ciclo de verificação com um TestClient real: em ambos os casos a exceção escapa
      até o chamador (500 não tratado), e no caso de db.salvar isso derruba também uma
      segunda URL do mesmo lote que já tinha sido processada com sucesso — exatamente o
      cenário que L-02 proíbe. Já documentado como CR-01 em 05-REVIEW.md (Critical).
    artifacts:
      - path: "app/main.py"
        issue: "gerar_briefings captura apenas FetchError (linha 127); db.salvar (linha 125) e Briefing(**dados) no caminho de cache (linha 110) não têm guarda alguma"
    missing:
      - "Envolver db.salvar(...) e o Briefing(**dados) do caminho de cache em tratamento que degrada a URL individual (ex.: item de falha ou miss de cache), sem propagar a exceção para fora do laço"
human_verification: []
---

# Phase 5: LLM Verification Report

**Phase Goal:** Ligar o `LLMExtractor` com saída estruturada validada, seleção automática entre
LLM e heurístico, tratamento de erro e limite de caracteres, mais quatro correções de
estabilidade — de forma que, com chave, o briefing vem rico, e sem chave, cai no heurístico sem
quebrar (SPEC §15).
**Verified:** 2026-08-26 (offline; nenhuma chamada paga ao provedor foi feita nesta verificação)
**Status:** gaps_found
**Re-verification:** Não — verificação inicial.

## Goal Achievement

### Observable Truths — critério de pronto e escopo da fase (CONTEXT.md)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Com chave, o briefing vem rico (SPEC §15) | ✓ VERIFIED | Evidência já registrada em `05-05-SUMMARY.md` (Task 4, D-14): 2 URLs reais via Groq/`openai/gpt-oss-120b`, HTTP 200, `extrator: llm`, `dores_provaveis`/`ganchos_de_conversa` claramente específicos por página (bna.dev.br vs. fastapi.tiangolo.com, sem frase genérica repetida). Não reexecutado nesta verificação por restrição de chamada paga; a evidência gravada é suficientemente detalhada para aceitar sem repetir a chamada. |
| 2 | Sem chave, cai no heurístico sem quebrar (SPEC §15, L-05) | ✓ VERIFIED | `app/extractor.py::escolher_extrator()` linhas 241-249; `test_escolher_extrator_sem_chave_devolve_heuristico` passa (`.venv` pytest, 7/7 verde) |
| 3 | `main.py` — escolha de extrator por URL, dentro do laço, com `try/except` caindo no heurístico | ⚠️ PARCIAL | `_extrair_com_fallback` (main.py:46-84) cumpre isto para exceções do próprio extrator (testado por `test_extrator_que_falha_nao_derruba_a_requisicao`). Mas o `try/except` do laço externo (main.py:118-136) só cobre `FetchError` — falhas fora do extrator (gravação em cache, desserialização de cache) **não** caem no heurístico, escapam e derrubam o lote. Ver gap L-02 abaixo. |
| 4 | `static/index.html` — mojibake corrigido e BOM removido | ✓ VERIFIED | Leitura de bytes crus: `BOM present: False`; nenhuma ocorrência de `0xC3 0x83` no arquivo; strings `reunião`, `confiança:`, `Dores prováveis` presentes em UTF-8 correto |
| 5 | `fetcher.py` — timeout na leitura do `robots.txt` | ✓ VERIFIED | `ROBOTS_TIMEOUT = 5.0` (fetcher.py:23); `pode_raspar()` usa `httpx.get(..., timeout=ROBOTS_TIMEOUT)` em vez de `RobotFileParser.read()` (fetcher.py:36-48), fail-open preservado |
| 6 | `main.py` — caminho absoluto em `StaticFiles` e `FileResponse` | ✓ VERIFIED | `BASE_DIR`/`STATIC_DIR` derivados de `Path(__file__).resolve()` (main.py:30-31); usados em `app.mount(...)` (linha 158) e `FileResponse(STATIC_DIR / "index.html")` (linha 163) |
| 7 | `LLMExtractor` implementado, com saída estruturada e prompt endurecido | ✓ VERIFIED | `app/extractor.py::LLMExtractor` completo: `_montar_mensagens` (D-11), `_chamar_provedor` (D-02/D-03), `extrair` (validação L-03). Sem `NotImplementedError` residual. |
| 8 | Visibilidade da degradação para o vendedor (D-05..D-08) | ✓ VERIFIED | `BriefingResponse.degradado` (schemas.py:59-62); mensagem curta em `_extrair_com_fallback` (main.py:68-77); `.tag-aviso` condicional em `index.html` (linhas 29, 98); `/health` com `llm_disponivel` (main.py:39-43) |
| 9 | Regra de upgrade de extrator no cache (D-09/D-10) | ✓ VERIFIED | `db.buscar(url, llm_disponivel=False)` (db.py:41-63): linha `heuristico` vira miss quando `llm_disponivel=True`; `criar_tabelas()` intocado, nenhuma DDL destrutiva no arquivo |

**Score desta seção:** 8/9 (1 parcial, que se resolve na falha de L-02 abaixo)

### Cobertura de Requisitos — L-01..L-06, D-01..D-14 (fonte: `05-CONTEXT.md`)

Este projeto não tem `REQUIREMENTS.md`/`ROADMAP.md` (decisão de processo registrada no topo de
`05-CONTEXT.md`); os IDs de decisão travada fazem esse papel.

| ID | Descrição resumida | Status | Evidência |
|---|---|---|---|
| L-01 | Extrator atrás da interface `Extractor`, heurístico como fallback | ✓ VERIFIED | `Extractor(Protocol)` (extractor.py:53-58); `HeuristicExtractor` e `LLMExtractor` cumprem `nome`/`extrair` |
| L-02 | Fallback **por URL**, não por lote | ✗ FAILED | Reproduzido nesta verificação: (a) `db.salvar` levantando exceção derruba a requisição inteira, inclusive uma segunda URL do mesmo lote já processada com sucesso; (b) `Briefing(**dados)` no caminho de cache (main.py:110) levantando `ValidationError` também escapa sem tratamento. Ver seção "Gaps" abaixo para os comandos de reprodução. |
| L-03 | Saída do LLM validada pelo schema `Briefing`; formato inválido levanta erro | ✓ VERIFIED | `extractor.py:233-238` — `Briefing(**dados)`, `except (TypeError, ValidationError): raise LLMError(...)` |
| L-04 | Corte de 12 mil caracteres no texto enviado ao modelo | ✓ VERIFIED | `config.LLM_MAX_CHARS` (config.py:37, padrão 12000); consumido em `_montar_mensagens` (extractor.py:116) |
| L-05 | Sem chave configurada, roda no heurístico sem quebrar | ✓ VERIFIED | `escolher_extrator()`; `test_escolher_extrator_sem_chave_devolve_heuristico` passa |
| L-06 | Stack não muda (FastAPI, SQLite, HTML servido pela API) | ✓ VERIFIED | Nenhuma dependência nova; `requirements.txt` não tocado (confirmado nos SUMMARYs e pelos criteria de aceite de cada plano) |
| D-01 | `httpx` direto, não SDK do provedor | ✓ VERIFIED | `extractor.py` usa `httpx.Client` diretamente (linhas 185-192), sem pacote novo |
| D-02 | `response_format: json_schema` derivado de `Briefing.model_json_schema()` + validação na volta; degrada para JSON pedido no prompt | ✓ VERIFIED (caminho primário verificado ao vivo; galho de degradação coberto só por duplo) | `_chamar_provedor` monta `response_format` a partir do schema Pydantic (extractor.py:169-182); degradação única via `_SemJsonSchema` (extractor.py:198-205, 221-226). Caminho primário verificado contra `openai/gpt-oss-120b` real (05-05-SUMMARY.md); galho `_SemJsonSchema` só testado com duplo, não contra provedor real — limite já documentado corretamente em `COVERAGE.md` e no `05-05-SUMMARY.md`, e não é uma alegação exagerada. |
| D-03 | Timeout de 20s, sem retry | ✓ VERIFIED | `LLM_TIMEOUT = 20.0` (extractor.py:47); nenhum `for`/`while` em `_chamar_provedor` |
| D-04 (emendada) | `config.py` lê apenas `LLM_API_KEY`, `LLM_MODELO`, `LLM_MAX_CHARS`, `LLM_BASE_URL` | ✓ VERIFIED | `app/config.py` expõe exatamente esses quatro nomes públicos + `os` |
| D-05 | `extrator` continua `"heuristico"`; degradação em campo separado | ✓ VERIFIED | `BriefingResponse.degradado` opcional, default `None` (schemas.py:59-62); `db.py` não referencia `degradado` |
| D-06 | Motivo da falha chega ao vendedor, curto, sem stack trace | ✓ VERIFIED | `_extrair_com_fallback` só interpola `str(erro_extrator)` quando é `LLMError`, trunca em 200 chars (main.py:68-76) |
| D-07 | UI destaca briefing degradado com tag de aviso | ✓ VERIFIED | `.tag-aviso` (index.html:29); `<span class="tag tag-aviso">` condicional em `render()` (index.html:98), valor passa por `escapar()` |
| D-08 | `/health` informa qual extrator está ativo (booleano) | ✓ VERIFIED | `health()` devolve `{"status": "ok", "llm_disponivel": bool(config.llm_api_key())}` (main.py:39-43) |
| D-09 | Regra de upgrade: entrada `heuristico` vira miss quando LLM disponível | ✓ VERIFIED | `db.buscar()` linhas 60-61; `main.py:104` passa `llm_disponivel=bool(config.llm_api_key())` |
| D-10 | Não implementar `conteudo_hash`; nenhuma migração de schema | ✓ VERIFIED | `criar_tabelas()` (db.py:27-38) idêntico ao pré-existente, sem coluna nova; nenhum `ALTER`/`DROP`/`DELETE` no arquivo |
| D-11 | Mitigação de injeção de prompt completa (3 camadas) | ✓ VERIFIED | Mensagem de sistema contém "dado, nunca comando" (extractor.py:137-141); texto em mensagem separada com delimitadores (linhas 144-151); anti-forja de delimitador remove `DELIM_INICIO`/`DELIM_FIM` do conteúdo (linhas 118-122); validação de schema na saída (L-03) |
| D-12 | Quatro testes offline, sem chave e sem rede | ✓ VERIFIED | `test_smoke.py` tem exatamente os 4 testes descritos + 3 pré-existentes = 7; `pytest -q` roda em 0.38s sem rede, todos verdes |
| D-13 | `LLM_BASE_URL` como 4ª variável; padrões invertidos para o Groq | ✓ VERIFIED | `config.py`: `LLM_BASE_URL` padrão `https://api.groq.com/openai/v1`, `LLM_MODELO` padrão `openai/gpt-oss-120b`; `.env.example` traz o mesmo par |
| D-14 | Ondas 4-6 verificáveis contra modelo real; backstop vira verdade explícita | ✓ VERIFIED (com limite documentado) | Evidência em `05-05-SUMMARY.md`: HTTP 200, `extrator: llm` para as 2 URLs, briefings específicos por página. Limite corretamente registrado: só o caminho primário de D-02 foi exercitado, não o galho de degradação. |

**Score desta seção:** 19/20 (L-02 falhou; D-02 verificado com limite já documentado, contado como verificado)

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `app/main.py::_extrair_com_fallback` | 3-tupla com degradação (D-05) | ✓ VERIFIED | Presente, testado |
| `app/main.py::BASE_DIR`/`STATIC_DIR` | Caminho absoluto | ✓ VERIFIED | Presente, testado a partir de cwd diferente |
| `app/extractor.py::LLMExtractor` | Chamada real, validação, prompt endurecido | ✓ VERIFIED | Completo, sem stub |
| `app/config.py` | 4 variáveis | ✓ VERIFIED | `llm_api_key()`, `LLM_MODELO`, `LLM_MAX_CHARS`, `LLM_BASE_URL` |
| `.env.example` | 4 linhas, sem segredo | ✓ VERIFIED | Confirmado via leitura de bytes; sem padrão `sk-`/`gsk_` |
| `app/schemas.py::BriefingResponse.degradado` | Campo opcional | ✓ VERIFIED | `Field(default=None, ...)` |
| `app/db.py::buscar(url, llm_disponivel)` | Regra de upgrade | ✓ VERIFIED | Presente, comportamento confirmado |
| `static/index.html::.tag-aviso` | Tag CSS de aviso | ✓ VERIFIED | Presente, condicional, escapada |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `gerar_briefings` (laço) | `_extrair_com_fallback` | chamada por URL | ✓ WIRED | `escolher_extrator()` só é chamado dentro da função auxiliar, uma vez por URL |
| `gerar_briefings` (laço) | `db.salvar`/`Briefing(**dados)` | try/except | ✗ NOT_WIRED (parcial) | Guarda cobre apenas `FetchError`; exceções de `db.salvar` e de desserialização do cache não são tratadas — ver gap |
| `LLMExtractor._chamar_provedor` | `config.LLM_BASE_URL` | leitura de módulo | ✓ WIRED | Nenhuma constante de endpoint em `extractor.py`; endereço vem de `config` |
| `/health` | `config.llm_api_key()` | mesma fonte de `escolher_extrator()`/cache | ✓ WIRED | Os três pontos consultam a mesma função |
| `render()` (index.html) | `r.degradado` | span condicional escapado | ✓ WIRED | `escapar(r.degradado)` ocorre exatamente uma vez, dentro do ternário |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| `pytest -q` roda 7 testes offline | `.venv/Scripts/python.exe -m pytest -q` | `7 passed` em 0.38s | ✓ PASS |
| `static/index.html` sem BOM/mojibake | leitura de bytes crus | `BOM: False`, `0xC3 0x83`: 0 ocorrências | ✓ PASS |
| `.env.example` sem segredo, 4 variáveis coerentes com `config.py` | leitura via `.venv` python | conteúdo bate exatamente com os padrões do código | ✓ PASS |
| L-02: um `db.salvar` que falha não derruba o lote | `TestClient.post(/api/briefings, ...)` com `db.salvar` monkeypatchado para levantar `RuntimeError` em uma das 2 URLs | Exceção **escapou** até o chamador; a URL boa do mesmo lote também foi perdida | ✗ FAIL |
| L-02: uma linha de cache antiga incompatível com o schema atual não derruba a requisição | `TestClient.post(/api/briefings, ...)` com `db.buscar` devolvendo um dict sem o campo `empresa` | `ValidationError` **escapou** até o chamador (não virou item de falha) | ✗ FAIL |

### Requirements Coverage

Ver tabela "Cobertura de Requisitos — L-01..L-06, D-01..D-14" acima. 19/20 IDs verificados; L-02
falhou.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `app/main.py` | 118-136 | `except FetchError` não cobre `db.salvar`/desserialização de cache | 🛑 Blocker | Viola L-02 (locked decision); reproduzido nesta verificação |
| `app/schemas.py` | 58 | `extrator: str` em vez de `Literal["llm", "heuristico", "falha"]` | ⚠️ Warning | Sem enforcement do enum fechado da SPEC §8; já sinalizado como WR-01 em `05-REVIEW.md` |
| `test_smoke.py` | (arquivo todo) | Sem teste de unidade dedicado para a regra de upgrade de cache (D-09), para o galho de degradação `_SemJsonSchema` (D-02) via duplo `httpx`, e para a anti-forja de delimitador (D-11) | ⚠️ Warning | Comportamento crítico coberto só por script ad-hoc executado durante o plano, não persistido na suite; já sinalizado como WR-02 em `05-REVIEW.md` |
| `app/main.py` | 78-84 | Braço de dupla falha interpola `str(erro_heuristico)` sem `isinstance` guard | ℹ️ Info | Hoje inofensivo porque `HeuristicExtractor.extrair()` é livre de exceção nas entradas atuais; já sinalizado como WR-03 em `05-REVIEW.md` |
| — | — | Nenhum `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` real encontrado | — | Os matches de grep foram falsos positivos (`todos`, `placeholder=` de atributo HTML, `todo` dentro de "atende... todo o Brasil") |

Nenhum pacote novo foi instalado nesta fase (`requirements.txt` intocado em todos os 7 planos).

### Human Verification Required

Nenhum item pendente de verificação humana. O julgamento de especificidade do "briefing rico"
(D-14) já foi feito pelo executor durante o plano 05 e está registrado com evidência concreta e
comparável (duas listas de `dores_provaveis` claramente não intercambiáveis) em
`05-05-SUMMARY.md`; não há necessidade de repetição.

### Gaps Summary

**Um blocker real, já antecipado no code review (CR-01) e confirmado nesta verificação por
reprodução direta.**

`L-02` é uma decisão travada, explicitamente marcada "NÃO reabrir" em `05-CONTEXT.md": *"Fallback
por URL, não por lote. Um link ruim não contamina os outros."* O plano 05-01 implementou a
degradação em três degraus (extrator escolhido → heurístico → briefing de falha) **apenas para
exceções levantadas pelo próprio extrator**. O laço externo em `gerar_briefings`
(`app/main.py:118-136`) continua capturando somente `FetchError`. Duas rotas de exceção
independentes do extrator escapam desse guarda:

1. `db.salvar(url, briefing.model_dump(), nome_extrator)` (linha 125) — uma falha de escrita em
   SQLite (ex.: `sqlite3.OperationalError: database is locked`, plausível sob escrita concorrente,
   já que o SQLite serializa gravações) propaga sem tratamento.
2. `Briefing(**dados)` no caminho de leitura do cache (linha 110) — uma linha gravada por uma
   versão anterior do schema `Briefing` (algo que se torna mais provável à medida que o projeto
   ganha mais fases) levanta `ValidationError` sem tratamento.

Reproduzi os dois cenários nesta verificação com `TestClient` real (comandos documentados acima,
na seção "Behavioral Spot-Checks"): em ambos os casos a exceção escapa até o chamador do FastAPI
— e no caso de `db.salvar`, uma segunda URL do mesmo lote, já processada com sucesso, também é
perdida junto. Isso é precisamente o que L-02 proíbe, e o próprio docstring de `gerar_briefings`
declara a garantia que está sendo quebrada: *"Um link que falha nao derruba os outros: cada URL e
tratada de forma independente"* (main.py:92-94).

Este achado já estava documentado como Critical (CR-01) em `05-REVIEW.md`, mas nenhum dos 7 planos
da fase o corrigiu — o code review rodou depois da execução de todos os planos e a lacuna nunca foi
fechada por um plano de fechamento. O fix sugerido no próprio `05-REVIEW.md` é direto: alargar o
`try/except` do laço para cobrir exceções de armazenamento/desserialização e degradar aquela URL
individualmente, e envolver o `Briefing(**dados)` do caminho de cache num `try/except
(ValidationError, TypeError)` que trata a linha como cache-miss em vez de propagar.

**Nenhum outro item bloqueia o objetivo da fase.** As 8 correções/entregas restantes do escopo
(4 correções de estabilidade, `LLMExtractor` ligado e verificado contra modelo real, visibilidade
de degradação, regra de upgrade de cache, config/`.env.example`) estão implementadas, testadas e
consistentes com o código em disco — não apenas com o que os SUMMARYs alegam. Os três achados de
warning/info do `05-REVIEW.md` (WR-01, WR-02, WR-03) permanecem válidos e não corrigidos, mas não
bloqueiam o objetivo declarado da fase; ficam registrados para follow-up.

**Sobre os limites já conhecidos e documentados (não são gaps novos, apenas confirmados como
corretamente caracterizados):**
- O galho de degradação `_SemJsonSchema` (D-02) não foi exercitado contra o Groq real — só por
  teste com duplo. `COVERAGE.md` e `05-05-SUMMARY.md` registram isso com precisão e não alegam mais
  do que foi verificado.
- A latência por URL não foi medida com precisão (bug de encoding cp1252 no console Windows
  abortou o script); só existe uma estimativa de ordem de grandeza (~3.0s) derivada de deltas de
  `coletado_em`. Também corretamente registrado como risco residual em `05-05-SUMMARY.md`.

---

_Verified: 2026-08-26_
_Verifier: Claude (gsd-verifier)_
