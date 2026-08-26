---
phase: 05-llm
plan: 02
subsystem: infra
tags: [httpx, robots-txt, encoding, utf-8, frontend]

# Dependency graph
requires: []
provides:
  - "pode_raspar() com timeout explicito de 5s na leitura do robots.txt, fail-open preservado"
  - "static/index.html em UTF-8 correto, sem BOM e sem duplo encode"
affects: [05-06, 05-07]

actuals:
  tokens: 560
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Leitura de robots.txt via httpx.get com timeout curto (ROBOTS_TIMEOUT=5.0), separado do timeout de fetch normal (TIMEOUT=15.0), alimentando RobotFileParser.parse() em vez de RobotFileParser.read()"

key-files:
  created: []
  modified:
    - "app/fetcher.py"
    - "static/index.html"

key-decisions:
  - "ROBOTS_TIMEOUT=5.0 como constante separada de TIMEOUT=15.0 (divergencia consciente do 05-PATTERNS.md, ja registrada no plano): reusar TIMEOUT significaria ate 30s por URL no pior caso"

patterns-established:
  - "Timeout curto e dedicado para requisicoes de metadado (robots.txt) que bloqueiam o trabalho de verdade, distinto do timeout de conteudo principal"

requirements-completed: [L-06]

coverage:
  - id: D1
    description: "pode_raspar() desiste em no maximo ~5s (ROBOTS_TIMEOUT) e devolve True (fail-open) para dominio lento ou inacessivel, mantendo a consulta real ao robots.txt"
    requirement: L-06
    verification:
      - kind: unit
        ref: "manual: python -c import time,app.fetcher... pode_raspar('https://10.255.255.1/pagina') is True em <12s (2.3s observado)"
        status: pass
      - kind: unit
        ref: "pytest -q (test_smoke.py, 3 testes)"
        status: pass
    human_judgment: false
  - id: D2
    description: "static/index.html reescrito em UTF-8 sem BOM e sem duplo encode; reunião, confiança e Dores prováveis corretos; escapar() e demais estruturas intactas"
    requirement: L-06
    verification:
      - kind: unit
        ref: "manual: leitura de bytes crus confirmando ausencia de BOM, ausencia de 0xC3 0x83, presenca das strings UTF-8 corretas e <meta charset=\"utf-8\">"
        status: pass
    human_judgment: true
    rationale: "Renderizacao visual correta num navegador/projetor exige confirmacao humana; a verificacao automatizada cobre apenas os bytes, nao a exibicao final na tela"

duration: 10min
completed: 2026-08-26
status: complete
---

# Phase 5 Plan 2: Timeout no robots.txt e correção do mojibake em index.html Summary

**`pode_raspar()` agora usa `httpx.get(timeout=5.0)` em vez de `RobotFileParser.read()` sem timeout, e `static/index.html` foi reescrito em UTF-8 correto (sem BOM, sem duplo encode) nas três strings acentuadas que apareciam corrompidas na tela.**

## Performance

- **Duration:** ~10min
- **Started:** 2026-08-26T14:31 (após conclusão do plano 05-01, wave 1)
- **Completed:** 2026-08-26T14:40
- **Tasks:** 2/2 completas
- **Files modified:** 2

## Accomplishments
- `app/fetcher.py::pode_raspar()` não usa mais `RobotFileParser.read()` (sem timeout); a leitura passa por `httpx.get(robots_url, timeout=ROBOTS_TIMEOUT, ...)`, alimentando `RobotFileParser.parse()` com as linhas do corpo. Fail-open preservado (`except Exception: return True`, e `status_code >= 400` também devolve `True`).
- Novo domínio não roteável (`10.255.255.1`) confirma o limite: `pode_raspar()` devolve `True` em ~2.3s, bem abaixo do limite de 12s do critério de aceite.
- `static/index.html` corrigido em 3 pontos exatos (linhas 39, 96, 102): `reunião`, `confiança:` e `Dores prováveis`, agora em UTF-8 correto. Confirmado ao nível de byte: sem BOM (`EF BB BF`), zero ocorrências de `C3 83` (antes havia 3).
- Nenhuma outra linha do HTML foi tocada: `escapar()`, `render()`, `lista()`, o `fetch` de `/api/briefings` e `<meta charset="utf-8">` permanecem idênticos.

## Task Commits

Each task was committed atomically:

1. **Task 1: Timeout na leitura do robots.txt** - `7889c57` (fix)
2. **Task 2: Corrigir o duplo encode em static/index.html** - `1281e40` (fix)

_Nenhuma task TDD neste plano; ambas `type="auto"`._

## Files Created/Modified
- `app/fetcher.py` - nova constante `ROBOTS_TIMEOUT = 5.0` e corpo de `pode_raspar()` reescrito sobre `httpx.get` + `RobotFileParser.parse()`
- `static/index.html` - três strings de texto corrigidas (`reunião`, `confiança:`, `Dores prováveis`), reescrito em UTF-8 sem BOM

## Decisions Made
- Mantida a divergência consciente já registrada no plano: `ROBOTS_TIMEOUT = 5.0` como constante separada de `TIMEOUT = 15.0`, em vez de reaproveitar `TIMEOUT` como o `05-PATTERNS.md` sugeria — evita até 30s por URL no pior caso (robots + página).

## Deviations from Plan

### Discrepância no critério de aceite (não corrigida por ser miscontagem do plano, não defeito de código)

**1. Contagem de chamadas a `escapar(` no critério de aceite da Task 2**
- **Encontrado durante:** Task 2, ao rodar o `<verify><automated>` do plano.
- **Discrepância:** o script de verificação do plano exige `d.count(b'escapar(') >= 8`. O arquivo tem e sempre teve **7** ocorrências da substring `escapar(` (6 chamadas + a própria definição `function escapar(s)`), confirmado via `git show HEAD~1:static/index.html | grep -c 'escapar('` no estado do arquivo **antes** desta task — ou seja, o número não mudou com esta edição, nenhuma chamada foi removida.
- **Ação tomada:** nenhuma. Não foi adicionada uma chamada `escapar()` artificial só para bater o número 8 — isso violaria a restrição dura do próprio plano ("Não altere nenhuma outra linha") e introduziria uma mudança estrutural não pedida. O invariante real que a task protege — nenhuma chamada a `escapar()` removida, defesa de XSS intacta — está verificado e intacto (7 antes, 7 depois).
- **Demais critérios de aceite da Task 2:** todos passaram (sem BOM, zero `C3 83`, as três strings corretas em UTF-8, `b.confianca`/`b.dores_provaveis` sem acento no JS com contagem 1 cada, `<meta charset="utf-8">` presente, `pytest -q` verde, 115 linhas mantidas).
- **Arquivos:** `static/index.html`
- **Commit:** `1281e40`

---

**Total deviations:** 1 registrada (discrepância de critério de aceite pré-existente no plano, sem ação de código).
**Impact on plan:** Nenhum impacto funcional — o comportamento e a estrutura do arquivo estão exatamente como o plano pediu; a única lacuna é um número no script de verificação do próprio plano que não reflete o estado real (nem antes, nem depois desta task).

## Issues Encountered
Nenhum outro além da discrepância documentada acima.

## User Setup Required
None - nenhuma configuração de serviço externo necessária.

## Next Phase Readiness
- `app/fetcher.py` e `static/index.html` prontos para os planos seguintes da fase (06 toca `index.html` novamente para a tag de aviso de degradação, D-07 — este plano não antecipou nada daquele trabalho).
- `app/main.py` não foi tocado, conforme escopo declarado (`files_modified` do plano 02).
- Nenhum bloqueio para os próximos planos da wave.

---
*Phase: 5-LLM*
*Completed: 2026-08-26*

## Self-Check: PASSED

- FOUND: app/fetcher.py
- FOUND: static/index.html
- FOUND: .planning/phases/05-llm/05-02-SUMMARY.md
- FOUND commit: 7889c57
- FOUND commit: 1281e40
