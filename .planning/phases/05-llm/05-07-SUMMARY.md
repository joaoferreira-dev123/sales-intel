---
phase: 05-llm
plan: 07
subsystem: cache
tags: [cache, upgrade-de-extrator, sqlite, disponibilidade-llm]

requires:
  - phase: 05-llm (plano 04)
    provides: "app/config.py::llm_api_key() — fonte unica de disponibilidade do LLM"
  - phase: 05-llm (plano 06)
    provides: "app/main.py com from . import config, db ja no bloco de imports; /health::llm_disponivel usando a mesma fonte"
provides:
  - "app/db.py::buscar(url: str, llm_disponivel: bool = False) — entrada gravada por heuristico vira miss quando o LLM esta disponivel (D-09)"
  - "app/main.py::gerar_briefings consultando o cache com llm_disponivel=bool(config.llm_api_key()), avaliado dentro do laco por URL"
affects: []

actuals:
  tokens: 700
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "regra de upgrade vive na leitura do cache (buscar()), nunca no schema — CREATE TABLE permanece byte-identico"
    - "disponibilidade do LLM avaliada dentro do laco por URL, mesma fonte (config.llm_api_key()) consultada por escolher_extrator() e /health"
    - "parametro novo com default False preserva 100% dos chamadores e testes existentes sem edicao"

key-files:
  created: []
  modified:
    - app/db.py
    - app/main.py

key-decisions:
  - "D-09: buscar() recebe llm_disponivel (default False); entrada extrator='heuristico' vira miss quando llm_disponivel=True; entrada extrator='llm' mantem a validade normal de 7 dias nos dois casos"
  - "D-10: nenhuma coluna criada/alterada/removida; criar_tabelas() intocado; briefings.db nao foi apagado nem recriado (verificado por tamanho e mtime antes/depois)"

requirements-completed: [D-09, D-10]

coverage:
  - id: D9
    description: "buscar() com o parametro llm_disponivel (default False); entrada heuristico vira miss com LLM disponivel; entrada llm mantem validade de 7 dias; main.py passa a mesma fonte de escolher_extrator()/health"
    requirement: "D-09"
    verification:
      - kind: unit
        ref: "script inline do <verify> da Task 1 sobre banco temporario: default mantem comportamento antigo, heuristico+llm_disponivel=True vira None, llm+llm_disponivel=True/False continua tupla -> ok"
        status: pass
      - kind: unit
        ref: "python -c inline: TestClient end-to-end — cache heuristico + LLM_API_KEY setada -> origem == 'novo' (recoleta acionada), com buscar_html mockado para nao bater na rede"
        status: pass
      - kind: unit
        ref: "grep -c 'db.buscar(url, llm_disponivel=' app/main.py -> 1; grep -v comentario 'db.buscar(url)' -> 0"
        status: pass
    human_judgment: false
  - id: D10
    description: "nenhuma DDL destrutiva; criar_tabelas() sem diff; briefings.db intacto"
    requirement: "D-10"
    verification:
      - kind: unit
        ref: "grep -v '^\\s*#' app/db.py | grep -ciE 'alter table|drop table|delete from|os\\.remove|unlink' -> 0"
        status: pass
      - kind: unit
        ref: "git diff app/db.py: hunk unico dentro de buscar(), nenhuma linha dentro de criar_tabelas()"
        status: pass
      - kind: unit
        ref: "stat briefings.db antes e depois das duas tasks: Size 12288 e Modify identicos (arquivo nao tocado)"
        status: pass
    human_judgment: false

duration: ~8min
completed: 2026-08-26
status: complete
---

# Phase 5 Plan 07: Regra de upgrade de extrator no cache Summary

**Com o LLM disponível, uma entrada de cache gravada pelo heurístico deixa de ser servida — `buscar()` a trata como ausente e força recoleta com o extrator melhor, enquanto entradas gravadas pelo LLM continuam valendo os 7 dias normais, tudo sem tocar em uma linha de schema.**

## Performance

- **Duration:** ~8 min
- **Tasks:** 2/2
- **Files modified:** 2 (`app/db.py`, `app/main.py`)

## Accomplishments
- `db.buscar()` ganhou o parâmetro `llm_disponivel: bool = False`: entrada gravada com `extrator="heuristico"` volta `None` quando `llm_disponivel=True`, forçando recoleta; entrada `extrator="llm"` continua seguindo a validade normal de 7 dias nos dois casos (D-09)
- O default `False` preserva 100% dos chamadores e testes existentes sem edição — inclusive `test_extrator_que_falha_nao_derruba_a_requisicao`, cujo monkeypatch de `db.buscar` já usa assinatura tolerante (`*args, **kwargs`) desde o plano 03
- `main.py::gerar_briefings` passa a consultar o cache com `db.buscar(url, llm_disponivel=bool(config.llm_api_key()))`, avaliado **dentro do laço**, por URL — mesma fonte já consultada por `escolher_extrator()` e por `/health`, para que os três nunca discordem sobre o modo de operação
- `criar_tabelas()` permanece byte-idêntico: a regra vive inteiramente na leitura do cache, nunca no schema (D-10)
- Verificação end-to-end confirmada: com `LLM_API_KEY` no ambiente, uma URL cuja última coleta foi `heuristico` deixa de vir do cache (`origem == "novo"`, recoleta acionada); sem a chave, o comportamento é idêntico ao de antes da fase (`origem == "cache"`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Regra de upgrade de extrator na leitura do cache (D-09, D-10)** - `4b6ebe3` (feat)
2. **Task 2: main.py informa a disponibilidade do LLM ao consultar o cache** - `cafd41a` (feat)

## Files Created/Modified
- `app/db.py` - `buscar(url: str, llm_disponivel: bool = False)`: nova condição de miss após a checagem de validade existente, comentário inline explicando o porquê (`# heuristico com LLM ligado: forca recoleta para subir a qualidade`); docstring estendida em uma frase; `criar_tabelas()` e o restante do arquivo intocados
- `app/main.py` - a chamada `cache = db.buscar(url)` dentro do laço de `gerar_briefings` virou `cache = db.buscar(url, llm_disponivel=bool(config.llm_api_key()))`, com comentário inline citando a fonte única compartilhada com `escolher_extrator()` e `/health`; `from . import config, db` já existia desde o plano 06, nenhum import novo necessário

## Decisions Made
- D-09 seguiu o plano à risca: parâmetro com default `False`, condição de miss logo após a checagem de validade que já existia, mesmo estilo de comentário inline (`# existe, mas venceu` → `# heuristico com LLM ligado: ...`).
- D-10 tratado como restrição dura: nenhum `ALTER TABLE`, `DROP TABLE`, `DELETE FROM`, `os.remove` ou `unlink` em `app/db.py` (confirmado por grep negativo); `briefings.db` conferido por tamanho (12288 bytes) e data de modificação idênticos antes e depois das duas tasks.
- Avaliação de disponibilidade feita dentro do laço `for url_obj in req.urls`, não antes dele — mesmo raciocínio de L-02 (fallback por URL, não por lote) já aplicado a `escolher_extrator()` no plano 01.

## Deviations from Plan

None - plano executado exatamente como escrito. Nenhuma acceptance criteria automatizada divergiu do esperado; nenhum teste novo foi adicionado a `test_smoke.py` (D-12 já fixa quatro testes, e este plano deliberadamente não acrescenta um quinto — a regra de D-09 foi verificada por script inline sobre banco temporário, como o plano determinou).

## Issues Encountered

None.

## Known Stubs

None - nenhuma alteração introduz valor vazio hardcoded, placeholder ou componente sem fonte de dados real.

## Threat Flags

None - as três fronteiras de confiança tocadas neste plano (aplicação→`briefings.db`, ambiente→decisão de cache, `LLM_API_KEY`→decisão de cache) já estavam mapeadas no `<threat_model>` do próprio plano (T-05-36 a T-05-40), todas com disposição `mitigate` ou `accept` já registrada e cumprida pelas tasks.

## User Setup Required

None.

## Next Phase Readiness
- Suite `pytest -q` verde com 7 testes, todos offline (sem rede, sem chave, sem gravação em `briefings.db`).
- `briefings.db` intacto: mesmo tamanho e mesma data de modificação de antes deste plano; nenhuma linha perdida.
- Este é o último plano da Fase 5 (item 6 do `<execution_order>` do CONTEXT.md). Todos os seis itens da fase estão entregues: correções de estabilidade, testes do fallback, `config.py`, `LLMExtractor`, visibilidade de degradação e regra de upgrade de cache.
- Nenhum bloqueio identificado.

---
*Phase: 05-llm*
*Completed: 2026-08-26*

## Self-Check: PASSED
- FOUND: app/db.py
- FOUND: app/main.py
- FOUND: .planning/phases/05-llm/05-07-SUMMARY.md
- FOUND commit: 4b6ebe3 (Task 1)
- FOUND commit: cafd41a (Task 2)
