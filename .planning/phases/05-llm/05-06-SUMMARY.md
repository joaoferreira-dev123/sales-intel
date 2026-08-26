---
phase: 05-llm
plan: 06
subsystem: api
tags: [degradacao, contrato-api, ui, health-check]

requires:
  - phase: 05-llm (plano 01)
    provides: "app/main.py::_extrair_com_fallback (2-tupla) e o laco por URL em gerar_briefings"
  - phase: 05-llm (plano 05)
    provides: "app/extractor.py::LLMError, mensagens auditadas e seguras de interpolar"
provides:
  - "app/schemas.py::BriefingResponse.degradado: str | None — motivo da degradacao em campo proprio, separado da coluna extrator (D-05)"
  - "app/main.py::_extrair_com_fallback com assinatura -> tuple[Briefing, str, str | None]"
  - "app/main.py::health com o campo llm_disponivel (D-08)"
  - "static/index.html::.tag-aviso e a <span class=\"tag tag-aviso\"> condicional em render() (D-07)"
affects: ["05-llm plano 07 (regra de upgrade de cache pode consumir /health::llm_disponivel)"]

actuals:
  tokens: 1631
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "mensagem de degradacao interpola str(e) apenas quando a excecao e LLMError; qualquer outra excecao usa so a frase generica, truncada em 200 chars"
    - "campo opcional em BriefingResponse com default=None, seguindo o mesmo estilo Field(default=..., description=...) de Briefing.segmento"
    - "span condicional via operador ternario no template literal, reaproveitando o padrao ja usado na primeira tag de render()"
    - "/health le config.llm_api_key() em tempo de chamada, mesma fonte de escolher_extrator(), para nunca mentir sobre o modo de operacao"

key-files:
  created: []
  modified:
    - app/schemas.py
    - app/main.py
    - static/index.html
    - test_smoke.py

key-decisions:
  - "D-05: extrator permanece heuristico no caminho degradado; degradado e campo separado, sem tocar app/db.py nem /api/historico"
  - "D-06: str(e) so entra na mensagem quando a excecao e LLMError (mensagens auditadas no plano 05); qualquer outra excecao produz apenas a frase generica"
  - "D-07: .tag-aviso reaproveita a classe .tag existente, sem novas variaveis em :root"
  - "D-08: /health e extensao aditiva sobre a SPEC S10 ({status: ok} preservado); llm_disponivel e estritamente booleano, nunca a chave/prefixo/modelo"
  - "D-12: teste 3 (test_extrator_que_falha_nao_derruba_a_requisicao) foi estendido com 2 asserts novos, nao duplicado — suite continua com 7 testes"

requirements-completed: [D-05, D-06, D-07, D-08, D-12]

coverage:
  - id: D5-D6
    description: "BriefingResponse.degradado opcional (default None); _extrair_com_fallback devolve 3-tupla; mensagem curta interpola str(e) so quando LLMError, truncada em 200 chars; extrator permanece heuristico no caminho degradado"
    requirement: "D-05, D-06"
    verification:
      - kind: unit
        ref: "python -c inline: BriefingResponse sem degradado continua valido (default None); assinatura de _extrair_com_fallback confere via inspect.getsource"
        status: pass
      - kind: unit
        ref: "test_smoke.py::test_extrator_que_falha_nao_derruba_a_requisicao (estendido): degradado comeca com 'IA indisponivel', nao contem o texto da excecao original, extrator continua heuristico"
        status: pass
      - kind: unit
        ref: "grep -v '^\\s*#' app/db.py | grep -c degradado -> 0 (campo nao chega ao banco)"
        status: pass
    human_judgment: false
  - id: D7
    description: ".tag-aviso reaproveita .tag com var(--accent); render() emite <span class=\"tag tag-aviso\"> apenas quando r.degradado existe, valor via escapar(); arquivo continua UTF-8 sem BOM e sem sequencia 0xC3 0x83"
    requirement: "D-07"
    verification:
      - kind: unit
        ref: "python -c inline: bytes[:3] != BOM, count(0xC3 0x83) == 0, .tag-aviso presente, escapar(r.degradado) ocorre exatamente 1 vez, var(--accent) dentro da regra .tag-aviso"
        status: pass
      - kind: unit
        ref: "grep -c ':root' static/index.html -> 1 (nenhum bloco de variaveis novo)"
        status: pass
    human_judgment: false
  - id: D8
    description: "GET /health devolve {status: ok, llm_disponivel: bool}; le config.llm_api_key() em tempo de chamada; nunca expoe a chave"
    requirement: "D-08"
    verification:
      - kind: unit
        ref: "python -c inline via TestClient: sem LLM_API_KEY -> llm_disponivel False; com LLM_API_KEY -> True; chaves da resposta == {status, llm_disponivel}; valor da chave nunca aparece no corpo"
        status: pass
      - kind: unit
        ref: "grep -v '^\\s*#' app/main.py | grep -c os.getenv -> 0 (usa config.llm_api_key(), nao os.getenv direto)"
        status: pass
    human_judgment: false
  - id: D12
    description: "Suite continua com 4 testes de D-12 mais os 3 pre-existentes = 7 no total; teste 3 estendido, nenhum quinto teste criado"
    requirement: "D-12"
    verification:
      - kind: unit
        ref: "grep -c 'def test_' test_smoke.py -> 7"
        status: pass
      - kind: unit
        ref: ".venv/Scripts/python.exe -m pytest -q -> 7 passed, offline"
        status: pass
    human_judgment: false

duration: ~12min
completed: 2026-08-26
status: complete
---

# Phase 5 Plan 06: Visibilidade da degradação para o vendedor Summary

**Quando o LLM falha e o heurístico assume, o vendedor agora vê exatamente por quê: `BriefingResponse.degradado` carrega uma frase curta e auditada, o cartão exibe uma tag de aviso na cor de destaque, e `GET /health` deixa conferir o modo de operação antes de subir no palco — tudo sem tocar na enumeração `extrator` da SPEC §8.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 3/3
- **Files modified:** 4 (`app/schemas.py`, `app/main.py`, `static/index.html`, `test_smoke.py`)

## Accomplishments
- `BriefingResponse` ganhou o campo opcional `degradado: str | None` (D-05) — a coluna `extrator` e `/api/historico` continuam com a enumeração `llm` / `heuristico` / `falha` intacta, exatamente como a SPEC §8 exige
- `_extrair_com_fallback` agora devolve uma 3-tupla; a mensagem de degradação só interpola `str(e)` quando a exceção é `LLMError` (mensagens escritas e auditadas no plano 05) — qualquer outra exceção produz apenas a frase genérica, truncada em 200 caracteres (D-06)
- O cartão do briefing degradado ganhou `<span class="tag tag-aviso">`, visível a distância num projetor, reaproveitando a classe `.tag` existente com a cor de destaque já declarada em `:root` (D-07)
- `GET /health` passou a informar `llm_disponivel` (booleano, lido de `config.llm_api_key()` em tempo de chamada) — extensão aditiva sobre a SPEC §10, sem quebrar nenhum consumidor existente e sem nunca expor a chave (D-08)
- `test_extrator_que_falha_nao_derruba_a_requisicao` foi estendido (não duplicado) com as asserções do campo `degradado` — suite permanece com exatamente 7 testes, todos offline (D-12)

## Task Commits

Each task was committed atomically:

1. **Task 1: Campo de degradacao no contrato e o motivo chegando ao vendedor (D-05, D-06)** - `dd8d3e9` (feat)
2. **Task 2: Tag de aviso no cartao do briefing degradado (D-07)** - `eca6448` (feat)
3. **Task 3: /health informa qual extrator esta ativo (D-08)** - `7807945` (feat)

## Files Created/Modified
- `app/schemas.py` - `BriefingResponse.degradado: str | None = Field(default=None, ...)`
- `app/main.py` - `_extrair_com_fallback` estendido para `tuple[Briefing, str, str | None]`; `gerar_briefings` desempacota e passa `degradado` ao `BriefingResponse` do caminho novo; `health()` acrescenta `llm_disponivel`; import de `LLMError` e `config`
- `static/index.html` - regra CSS `.tag-aviso`; `<span class="tag tag-aviso">` condicional em `render()`
- `test_smoke.py` - `test_extrator_que_falha_nao_derruba_a_requisicao` estendido com 2 asserções novas

## Decisions Made
- D-05/D-06 seguiram o plano à risca: `degradado` opcional em `BriefingResponse`, mensagem curta que só interpola texto de `LLMError`, truncagem em 200 caracteres, comentário inline explicando o "porquê" da distinção `LLMError` × qualquer outra exceção.
- D-07: uma única regra CSS nova (`.tag-aviso`), sem novas variáveis em `:root`, sem tocar `lista()`, `escapar()` ou o `fetch`.
- D-08: campo estritamente booleano em `/health`, lido da mesma fonte que `escolher_extrator()` consulta (`config.llm_api_key()`), nunca `os.getenv` direto em `main.py`.

## Deviations from Plan

None - plano executado exatamente como escrito. Todas as acceptance criteria automatizadas (greps, asserts inline, `pytest -q`) passaram na primeira tentativa, sem necessidade de ajuste.

## Issues Encountered

None.

## Known Stubs

None - nenhum valor vazio hardcoded, nenhum placeholder, nenhum componente sem fonte de dados. `degradado` é `None` no caminho feliz (comportamento intencional, coberto por D-05) e populado com valor real no caminho degradado (coberto por teste).

## Threat Flags

None - as três fronteiras de confiança tocadas neste plano (API→navegador via `degradado`, exceção interna→texto ao vendedor, `/health`→cliente não autenticado) já estavam mapeadas no `<threat_model>` do próprio plano (T-05-30 a T-05-35), todas com disposição `mitigate` ou `accept` já registrada e cumprida pelas tasks.

## User Setup Required

None.

## Next Phase Readiness
- Plano 07 (regra de upgrade de cache, D-09) pode consumir `/health::llm_disponivel` como sinal de disponibilidade do LLM, se desejar, sem qualquer mudança neste plano.
- Suite `pytest -q` verde com 7 testes, todos offline (sem rede, sem chave).
- `static/index.html` continua UTF-8 sem BOM e sem a sequência de bytes `0xC3 0x83` (verificado byte a byte).
- Nenhum bloqueio identificado para o plano 07.

---
*Phase: 05-llm*
*Completed: 2026-08-26*
