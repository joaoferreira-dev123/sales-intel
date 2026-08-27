---
status: testing
phase: 06-auth
source: [06-VERIFICATION.md]
started: 2026-08-27T18:59:25Z
updated: 2026-08-27T18:59:25Z
---

## Current Test

number: 1
name: Fluxo visual completo da UI num navegador real — vendedor e admin
expected: |
  Fluxo visual completo funciona sem erro de console; a area de admin so aparece
  para o papel admin; nenhum HTML quebrado ou nao escapado aparece na tela mesmo
  com um username contendo aspas simples.
awaiting: user response

## Tests

### 1. Fluxo visual completo da UI num navegador real — vendedor e admin

Abrir a UI num navegador real e percorrer os dois papeis:

**Como vendedor:**
- Logar como vendedor.
- Confirmar que a secao de admin (`#admin`) nunca aparece no DOM renderizado.
- Colar um link e ler o cartao de briefing.

**Como admin:**
- Logar como admin.
- Confirmar que a tela de gerenciar usuarios funciona visualmente de ponta a
  ponta: listar, criar, ativar/desativar.
- Confirmar que o botao de sair funciona.

**Escape de aspas simples:** criar um usuario cujo username contenha aspas
simples (por exemplo `o'brien`) e confirmar que ele aparece corretamente na
lista, sem HTML quebrado e sem marcacao escapando para a tela.

expected: Fluxo visual completo funciona sem erro de console; a area de admin so aparece para o papel admin; nenhum HTML quebrado ou nao escapado aparece na tela mesmo com um username contendo aspas simples.
result: [pending]

why_human: `test_pagina_inicial_traz_tela_de_login`, `test_escapar_do_front_cobre_aspas_simples` e os testes `front_consome_*` verificam presenca de marcacao/JS e chamadas de rede via regex/parse estatico e um `TestClient` que nao executa JavaScript — nenhum deles renderiza a pagina num motor de browser real. A experiencia visual (estado de carregamento, layout, foco do teclado, comportamento real do `fetch` com cookies no navegador) nao tem evidencia automatizada nesta verificacao.

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
