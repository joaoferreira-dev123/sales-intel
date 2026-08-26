# Phase 5: LLM — Context

**Gathered:** 2026-08-26
**Status:** Ready for planning

> **Nota de processo:** este projeto não tem `.planning/ROADMAP.md`. `init.phase-op 5`
> retornou `phase_found: false`. A discussão foi conduzida usando
> `SPEC-sales-intel.md` §15 como roadmap efetivo, por decisão explícita do usuário
> sob restrição de prazo (apresentação ao cliente hoje às 17h). O scaffolding GSD
> completo (`/gsd-new-project`, `/gsd-map-codebase`) fica para depois da apresentação.

<domain>
## Phase Boundary

Ligar o `LLMExtractor` com saída estruturada validada, seleção automática entre LLM
e heurístico, tratamento de erro e limite de caracteres — mais quatro correções de
estabilidade que precedem a implementação do LLM.

**Pronto quando** (SPEC §15): com chave, o briefing vem rico; sem chave, cai no
heurístico sem quebrar.

**Entra nesta fase:**
1. `main.py` — escolha de extrator por URL, dentro do laço, com `try/except` caindo no heurístico
2. `static/index.html` — corrigir mojibake nos bytes e remover BOM
3. `fetcher.py` — timeout na leitura do `robots.txt`
4. `main.py` — caminho absoluto em `StaticFiles` e `FileResponse`
5. `LLMExtractor` implementado, com saída estruturada e prompt endurecido
6. Visibilidade da degradação para o vendedor
7. Regra de upgrade de extrator no cache

**Fora de escopo, por decisão do usuário — não implementar e não discutir:**
autenticação e admin (Fase 6), Postgres, React, conexão do SQLite (`db.py:61`),
depreciação do `on_event` (`main.py:28`), comparação automática entre extratores.

</domain>

<spec_lock>
## Requirements (locked via SPEC-sales-intel.md)

Requisitos travados em `SPEC-sales-intel.md`. Downstream agents **MUST** ler a SPEC
antes de planejar ou implementar. Seções que governam esta fase:

- **§9** — schema `Briefing`, o artefato central. Campo `confianca` é mecanismo
  anti-alucinação, não enfeite.
- **§11** — estratégia de extração com LLM: saída estruturada obrigatória, o que o
  prompt precisa cobrir, corte de ~12k chars, injeção de prompt como risco real.
- **§6** — resiliência: LLM indisponível não pode derrubar a requisição inteira.
- **§13** — variáveis de ambiente.
- **§15** — definição e critério de pronto da Fase 5.
- **§16** — riscos conhecidos e mitigações declaradas.

</spec_lock>

<locked_decisions>
## Decisões travadas pelo usuário — NÃO reabrir

Trazidas para a discussão já decididas. Downstream agents tratam como fixas:

- **L-01:** Extrator atrás da interface `Extractor`, heurístico como fallback.
- **L-02:** Fallback **por URL**, não por lote. Um link ruim não contamina os outros.
- **L-03:** Saída do LLM validada pelo schema `Briefing`. Formato inválido levanta
  erro em vez de entregar dado ruim ao vendedor.
- **L-04:** Corte de 12 mil caracteres no texto enviado ao modelo, por custo.
- **L-05:** Sem chave de API configurada, o sistema roda no heurístico sem quebrar.
- **L-06:** Stack não muda — FastAPI, SQLite, HTML servido pela própria API.

</locked_decisions>

<decisions>
## Implementation Decisions

### Provedor e saída estruturada

- **D-01:** `LLMExtractor` fala com o modelo via **`httpx` direto**, não via SDK do
  provedor. `httpx` já é dependência (usado por `fetcher.py`), então não entra pacote
  novo no `requirements.txt`, não há `pip install` antes da demo, e qualquer endpoint
  compatível com OpenAI serve — o que importa porque o provedor da chave que ainda
  não chegou é desconhecido.
  — **Reversibility:** reversible — trocar por SDK depois toca um arquivo só, que é
  exatamente a propriedade que a SPEC §7 item 4 atribui ao desenho da interface.

- **D-02:** Saída estruturada com **`response_format: json_schema` nativo, derivado de
  `Briefing.model_json_schema()`, mais validação `Briefing(**dados)` na volta**. Cinto
  e suspensório: o modelo já vem forçado ao formato e a validação Pydantic pega o
  resto. Se o provedor não suportar `json_schema`, degrada para JSON pedido no prompt
  com a mesma validação na saída.

- **D-03:** Timeout de **20s na chamada ao LLM, sem retry**. O fallback heurístico já
  é a estratégia de recuperação; retry só dobraria a espera do vendedor antes de
  entregar o mesmo resultado, e com 10 URLs poderia travar a demonstração por minutos.

- **D-04:** *(emendada em 2026-08-26, pré-execução — ver `<context_update>` no fim do
  arquivo; era três variáveis, passa a quatro)* Cria **`app/config.py` lendo apenas
  `LLM_API_KEY`, `LLM_MODELO`, `LLM_MAX_CHARS` e `LLM_BASE_URL`**, mais `.env.example`
  (item de "pronto" da §17). `LLM_BASE_URL` tem **padrão `https://api.openai.com/v1`** —
  o endpoint não pode ficar cravado no código, porque a chave que chegou é de outro
  provedor. `FETCH_TIMEOUT`, `CACHE_VALIDADE_DIAS` e `USER_AGENT` permanecem hardcoded
  nesta fase — pertencem a fases já entregues e testadas, e mexer nelas hoje é superfície
  de regressão sem retorno de demonstração. Fecha parcialmente a divergência da §13.
  — **Reversibility:** reversible — as demais variáveis migram para `config.py` depois
  sem tocar em chamador nenhum.

### Visibilidade da degradação

- **D-05:** Quando o LLM falha e cai no heurístico, `extrator` **continua `"heuristico"`**
  e a degradação é sinalizada por um **campo opcional novo em `BriefingResponse`**.
  Preserva a enumeração da §8 (`llm` / `heuristico` / `falha`) e mantém limpa a coluna
  do banco e o `/api/historico`.
  — **Reversibility:** costly — é campo em contrato de API já consumido pela UI;
  remover depois exige tocar `schemas.py`, `main.py` e `static/index.html` juntos.

- **D-06:** O motivo da falha **chega ao vendedor**, curto e sem stack trace (ex.: "IA
  indisponível, briefing gerado por regras"). Mesmo padrão que o `FetchError` já usa em
  `main.py:78`. Sem isso o vendedor lê um briefing pobre e conclui que o produto é
  ruim, em vez de entender que houve degradação.

- **D-07:** A UI **destaca o briefing degradado com tag de aviso** no cartão,
  reaproveitando a classe `.tag` existente com cor de atenção. `static/index.html` já
  vai ser tocado pelo mojibake, então o custo marginal é ~6 linhas. Torna a degradação
  legível à distância, num projetor.

- **D-08:** **`/health` passa a informar qual extrator está ativo** (campo booleano
  indicando se a chave foi vista). Permite conferir o modo de operação minutos antes de
  subir no palco, sem gerar briefing. Ressalva registrada: a §10 define `/health` como
  `{"status": "ok"}` — a mudança é **aditiva**, não quebra consumidor existente, mas é
  uma extensão do contrato especificado.

### Cache × troca de extrator *(decidido por Claude)*

- **D-09:** **Regra de upgrade de extrator no `buscar()`**: entrada gravada por
  `heuristico` é tratada como *miss* quando o LLM está disponível, forçando recoleta
  com o LLM. Entradas gravadas por `llm` seguem a validade normal de 7 dias.
  Sem essa regra, URLs já coletadas voltariam do cache marcadas `extrator: heuristico`
  mesmo com o LLM ligado — visível na tela durante a apresentação.

- **D-10:** **Não implementar `conteudo_hash` (SPEC §8) nesta fase.** `briefings.db` já
  existe com dados e `CREATE TABLE IF NOT EXISTS` não adiciona coluna a tabela
  existente — exigiria `ALTER TABLE` ou apagar o banco. Migração de schema horas antes
  da demonstração é risco sem retorno, ainda mais porque `conteudo_hash` resolve outro
  problema (página mudou), não este (extrator melhorou). D-09 não altera schema.

### Injeção de prompt e teste *(decidido por Claude)*

- **D-11:** **Mitigação de injeção implementada por completo**, conforme §11 e §16:
  system message com o papel e instrução explícita de nunca obedecer comandos vindos
  do conteúdo da página; texto da página em mensagem separada, dentro de delimitador
  explícito e rotulado como dado não confiável; validação de schema na saída (L-03).
  É redação de prompt, não arquitetura — custa minutos, a SPEC exige, e é um dos
  pontos mais fortes da apresentação para uma empresa que instala IA em cliente.

- **D-12:** **Quatro testes, todos sem chave e sem rede**, adicionados ao
  `test_smoke.py` existente:
  1. `escolher_extrator()` sem chave devolve `HeuristicExtractor` — trava L-05
  2. `escolher_extrator()` com chave devolve `LLMExtractor` — via monkeypatch de env
  3. extrator que levanta exceção → resposta **200** com item marcado como degradado —
     é o teste do bug crítico (hoje `main.py:75` só captura `FetchError`)
  4. `LLMExtractor.extrair()` sem chave levanta erro claro — pedido nominalmente na §14

  **Não** criar `tests/` com 4 arquivos (§12) nesta fase: reorganizar layout de teste
  agora é churn sem valor de demonstração. Divergência registrada abaixo.

### Chegada da chave de API *(2026-08-26, pré-execução)*

Contexto narrativo completo na seção de atualização de contexto, no fim do arquivo. As
decisões em si moram aqui, nesta seção, porque é ela que o gate de cobertura varre.

> **Não escreva o nome da tag de abertura desta seção em prosa aqui dentro** — nem entre
> crases. O parser de `check.decision-coverage-plan` trata a menção como uma nova tag de
> abertura e passa a contar o bloco a partir dela, descartando em silêncio tudo que veio
> antes. Custou uma contagem de 12 para 2 nesta fase, com o gate ainda reportando
> `passed: true`.

- **D-13:** **`LLM_BASE_URL` entra no `config.py` como quarta variável**, com padrão
  `https://api.openai.com/v1`. O provedor é o **Groq**, compatível com a API da OpenAI,
  então o endpoint não pode ser constante de módulo em `app/extractor.py` — vira
  `config.LLM_BASE_URL`. Emenda D-04, que travava três variáveis. **Estende a SPEC §13**,
  que lista oito variáveis e não inclui `LLM_BASE_URL`; extensão aditiva, registrada na
  tabela de divergências.
  — **Reversibility:** reversible — leitura de ambiente com padrão; remover depois toca
  um arquivo.
  — **Armadilha operacional:** padrão aponta para a OpenAI enquanto a chave real é do
  Groq. Exportar só `LLM_API_KEY` manda chave do Groq para a OpenAI e toma 401 — que
  degrada para o heurístico em vez de quebrar, mas degrada *silenciosamente* para quem
  não ler o aviso. O `.env.example` carrega a combinação verificada para que o caminho
  de cópia seja o caminho feliz.

- **D-14:** **As ondas 4–6 passam a ser verificáveis contra modelo real.** A verdade
  *"com chave, o briefing vem rico"* deixa de ser `verification: backstop` e vira verdade
  explícita nos `must_haves` do plano 05-05. Entra uma tarefa de verificação com 2 ou 3
  URLs reais, `autonomous: false`, que **pula com registro** quando não há chave em vez de
  falhar a fase.
  — `openai/gpt-oss-120b` é, na conta do usuário, o único modelo grande com suporte a
  `structured_outputs`; os demais só têm `json_mode`. Confirma o caminho primário de D-02
  e trava a escolha de modelo.
  — **Limite da verificação:** o galho de degradação de D-02 dispara só em HTTP 400
  citando `response_format`. Com `gpt-oss-120b` ele **não é exercitado** pela verificação
  com modelo real e continua coberto apenas por teste com duplo. "LLM verificado" não é
  "os dois caminhos de D-02 verificados".

### Claude's Discretion

Nenhuma pergunta foi respondida com "você decide". As áreas **B (Cache)** e
**D (Injeção e teste)** foram delegadas por inteiro ao Claude pelo usuário e estão
resolvidas em D-09 a D-12 acima. D-13 e D-14 vieram de informação trazida pelo usuário
depois do planejamento, não de delegação.

</decisions>

<execution_order>
## Ordem de execução e linha de corte

Ordenado por *o que quebra a demonstração se faltar*. Cada item é entregável sozinho,
então a pressão de tempo corta pela cauda sem deixar trabalho pela metade.

| # | Item | Se o tempo acabar aqui |
|---|---|---|
| 1 | 4 correções de estabilidade | ✅ Demo estável no heurístico, sem o crash |
| 2 | Testes 1–3 do fallback (D-12) | ✅ O caminho que segura tudo fica coberto |
| 3 | `config.py` + `.env.example` (D-04) | ✅ Item de "pronto" da §17 fechado |
| 4 | `LLMExtractor` (D-01, D-02, D-03, D-11) | ⬇️ **Linha de corte natural** |
| 5 | Visibilidade da degradação (D-05 a D-08) | ⬇️ Só rende com o LLM ligado |
| 6 | Regra de upgrade no cache (D-09) | ⬇️ Só rende com o LLM ligado |

**Escopo cortado explicitamente:** `conteudo_hash` (§8) · `config.py` com as 8
variáveis (§13 — entram 3) · `tests/` em 4 arquivos (§12) · `README.md`, `AI-LOG.md`,
`Dockerfile`, `docker-compose.yml` (§12, §17, §18 — Fase 7) · exportar briefing
(§4 item 8) · conjunto de avaliação de prompt (§11 — precisa de chave).

**Risco que o desenho não elimina — ~~sem a chave~~, RESOLVIDO em 2026-08-26:** a chave
chegou antes da execução (ver `<context_update>`). Os itens 4–6 **passam a ser
verificáveis contra um modelo real**: rodar 2 ou 3 URLs reais antes da apresentação.

A ordem **não muda por isso**. O item 1 conserta um crash que independe da chave, e a
garantia estrutural continua valendo — o caminho do LLM só consegue falhar *para dentro*
do caminho heurístico, e é isso que o item 2 trava. A chegada da chave transforma o item
2 de "única rede de segurança" em "rede de segurança verificada dos dois lados", o que
reforça a ordem em vez de inverter.

O risco residual deixa de ser "o prompt pode devolver formato inesperado" e passa a ser
**quota, latência e custo reais do provedor durante a demonstração ao vivo** — e o
caminho de degradação de D-02 (`json_schema` → JSON pedido no prompt) deixa de ser o
caminho esperado e passa a ser um galho que só dispara em HTTP 400, portanto **não
exercitado pela verificação com modelo real** e coberto apenas por teste com duplo.

</execution_order>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Especificação do projeto
- `SPEC-sales-intel.md` — especificação completa; requisitos travados, ler antes de planejar
- `SPEC-sales-intel.md` §9 — schema `Briefing`, artefato central da fase
- `SPEC-sales-intel.md` §11 — estratégia de extração com LLM, prompt, injeção, corte de caracteres
- `SPEC-sales-intel.md` §6 — resiliência e custo/latência
- `SPEC-sales-intel.md` §13 — variáveis de ambiente
- `SPEC-sales-intel.md` §15 — definição e critério de pronto da Fase 5
- `SPEC-sales-intel.md` §16 — riscos conhecidos, incluindo injeção de prompt

### Código que esta fase altera
- `app/extractor.py` — interface `Extractor`, `HeuristicExtractor`, `LLMExtractor` (esqueleto)
- `app/main.py` — orquestração; `try/except` em `:75`, seleção de extrator em `:47`
- `app/schemas.py` — `Briefing`, `BriefingResponse`
- `app/db.py` — `buscar()` em `:41`, `CREATE TABLE` em `:31`
- `app/fetcher.py` — `pode_raspar()` em `:34`
- `static/index.html` — render em `:89`, tags em `:93`
- `test_smoke.py` — 3 testes existentes

**Ausente:** não há `.planning/ROADMAP.md`, `PROJECT.md`, `REQUIREMENTS.md` nem
`.planning/codebase/`. A SPEC supre a função dos três primeiros nesta fase.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`httpx`** (`requirements.txt`, usado em `fetcher.py:46`): já é dependência — base de D-01, evita pacote novo antes da demo.
- **Interface `Extractor`** (`extractor.py:31`): `Protocol` já definido e cumprido pelo heurístico. `LLMExtractor` só precisa preencher `extrair()`.
- **Padrão de erro do `FetchError`** (`main.py:75-83`): já converte falha em briefing de confiança baixa com motivo no `resumo`. D-06 segue este padrão em vez de inventar outro.
- **Classe `.tag`** (`index.html:27`): base de D-07, sem CSS novo além da cor.
- **Corte de 12k** (`extractor.py:88`): `_trecho = texto[:12000]` já escrito, só falta consumir; passa a vir de `config.py` por D-04.
- **`Briefing.model_json_schema()`**: Pydantic gera o JSON Schema de graça — alimenta D-02 sem schema escrito à mão.

### Established Patterns
- **Falha vira resultado, não exceção HTTP** (§10, `main.py:75`): resultado parcial é melhor que erro 500. D-05/D-06 estendem isso ao LLM.
- **Funções puras testáveis sem rede** (`fetcher.extrair_texto`, `HeuristicExtractor.extrair`): §14 exige que teste não dependa de internet. D-12 respeita.
- **`confianca` sempre `baixa` no heurístico** (`extractor.py:60`): honestidade deliberada (§9). Um fallback herda essa marcação naturalmente.

### Integration Points
- `main.py:47` — `escolher_extrator()` sai de fora do laço e passa a ser por URL (correção 1)
- `main.py:75` — `except FetchError` ganha um segundo braço para falha de extrator
- `db.py:41` — `buscar()` recebe a regra de upgrade de extrator (D-09)
- `fetcher.py:34` — `parser.read()` ganha timeout (correção 3)
- `schemas.py:50` — `BriefingResponse` recebe o campo de degradação (D-05)
- `main.py:104,109` — `StaticFiles` / `FileResponse` passam a usar caminho absoluto (correção 4)

### Defeito confirmado que motiva a fase
`escolher_extrator()` devolve `LLMExtractor` assim que `LLM_API_KEY` existir, mas
`LLMExtractor.extrair()` termina em `NotImplementedError` (`extractor.py:89`) e
`main.py:75` só captura `FetchError`. Hoje o sistema funciona **porque** a chave não
chegou: no minuto em que alguém exportar a variável, toda requisição vira 500 e derruba
também as URLs que já haviam dado certo no mesmo lote. Corrigir isso é o item 1.

</code_context>

<specifics>
## Specific Ideas

- **Estado verificado no disco em 2026-08-26:** `pytest` verde, 3 testes, 0.16s. Único
  diff não commitado é a remoção do BOM em `static/index.html`.
- **Mojibake é real nos bytes**, não artefato de leitor: `reuni\xc3\x83\xc2\xa3o`,
  `confian\xc3\x83\xc2\xa7a` — duplo encode. O navegador renderiza "reuniÃ£o",
  "confianÃ§a", "Dores provÃ¡veis" na tela durante a apresentação.
- **`RobotFileParser.read()` não tem timeout** (`fetcher.py:34`). O `httpx` tem 15s, o
  `robots.txt` não tem nenhum — um domínio lento pendura a requisição. Risco de demo ao vivo.
- **Prioridade declarada pelo usuário:** demonstrável e estável acima de completo.
- **Corte explícito lê como escopo controlado; corte silencioso lê como esquecimento**
  (§4) — a tabela de escopo cortado acima existe para ser apresentada, não escondida.

</specifics>

<divergences>
## Divergências SPEC × disco

Levantadas na leitura de 2026-08-26. As três primeiras viraram decisão; as demais ficam registradas.

| SPEC | Disco | Tratamento |
|---|---|---|
| §8 coluna `conteudo_hash` | ausente em `db.py` | **Adiada** — D-10 |
| §12 `app/config.py` | ausente; `os.getenv` inline em `extractor.py:77` | **Parcial** — D-04 |
| §13 oito variáveis de ambiente | código lê 1, crava o resto | **Parcial** — D-04 (entram 3 das 8) |
| §13 não prevê `LLM_BASE_URL` | provedor real exige endpoint configurável | **Estende (aditivo)** — D-13; 4ª variável, fora das 8 da §13 |
| §12 `tests/` com 4 arquivos | `test_smoke.py` na raiz, 3 testes | **Adiada** — D-12 |
| §17 `.env.example` obrigatório | ausente | **Fecha** — D-04 |
| §10 `/health` = `{"status":"ok"}` | conforme | **Estende (aditivo)** — D-08 |
| §12 `README.md`, `AI-LOG.md`, Docker | ausentes | Fase 7 |
| §7 comparar as duas saídas | não existe mecanismo | Fora de escopo por decisão do usuário |

</divergences>

<deferred>
## Deferred Ideas

Levantado durante a discussão, pertence a outra fase. Não perder:

- **`conteudo_hash` na tabela `briefings`** (§8) — detectar página alterada. Exige
  `ALTER TABLE` num banco com dados. Fase 7 ou primeira janela sem demonstração marcada.
- **`config.py` com as oito variáveis da §13** — `FETCH_TIMEOUT`, `CACHE_VALIDADE_DIAS`,
  `USER_AGENT`, `DATABASE_URL`, `DEBUG`.
- **`tests/` em quatro arquivos** (§12) — `test_fetcher.py`, `test_extractor.py`,
  `test_cache.py`, `test_api.py`.
- **Conjunto de avaliação de prompt** (§11) — páginas com resultado esperado, rodadas a
  cada mudança de prompt. Sem isso, "melhorei o prompt" é opinião. Precisa de chave.
- **Comparação automática entre extratores** (§7 item 3) — fora de escopo por decisão
  explícita do usuário nesta fase.
- **Exportar briefing como texto para CRM/WhatsApp** (§4 item 8).
- **Fase 6 — autenticação e admin** (§15) — fora salvo se sobrar tempo, o que a linha
  de corte torna improvável.
- **Fase 7 — empacotamento** (§15) — Dockerfile, compose, README, AI-LOG.
- **Conexão SQLite não fechada** (`db.py:61`) — fora de escopo por decisão do usuário.
- **`@app.on_event` depreciado** (`main.py:28`) — fora de escopo por decisão do usuário.
- **Scaffolding GSD** — `/gsd-new-project` e `/gsd-map-codebase` para gerar
  `.planning/` completo. Depois da apresentação.

</deferred>

<context_update>
## Atualização de contexto — 2026-08-26, antes da execução

**A chave de API chegou.** Informado pelo usuário depois do planejamento e antes de
`/gsd-execute-phase`. Emenda D-04 e acrescenta D-13 e D-14. Os planos foram revisados
para refletir isto; nada aqui reabre L-01..L-06.

**Configuração real, verificada pelo usuário:**

```
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODELO=openai/gpt-oss-120b
LLM_MAX_CHARS=12000
```

**As decisões formais estão na seção de decisões**, na subseção *"Chegada da chave de
API"* — **D-13** (`LLM_BASE_URL` como quarta variável, padrão OpenAI, armadilha
operacional) e **D-14** (ondas 4–6 verificáveis, backstop vira verdade explícita, limite
da verificação quanto ao galho de degradação de D-02).

Ficam ali, e não aqui, por um motivo concreto: o gate `check.decision-coverage-plan` varre
apenas aquele bloco. Com D-13 e D-14 só nesta seção, o gate reportava `total: 12` e
passava — as duas decisões mais recentes ficavam invisíveis justamente para o gate que
existe para impedir decisão perdida. Decisão nova nesta fase vai para lá; esta seção
guarda a narrativa.

</context_update>

---

*Phase: 5-LLM*
*Context gathered: 2026-08-26*
*Context updated: 2026-08-26 (chave de API recebida — D-04 emendada, D-13 e D-14 acrescentadas)*
