# Phase 5: LLM - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-26
**Phase:** 5-LLM
**Areas discussed:** Provedor e saída estruturada, Visibilidade da degradação
**Areas delegated to Claude:** Cache × troca de extrator, Injeção de prompt e teste

---

## Seleção de áreas

Quatro áreas cinzentas apresentadas. O usuário selecionou duas para discutir e delegou
as outras duas.

| Área | Descrição | Selecionada |
|--------|-------------|----------|
| A. Provedor e saída estruturada | Qual SDK entra no requirements.txt e como o JSON é garantido | ✓ |
| B. Cache × troca de extrator | Briefing heurístico em cache servido com o LLM ligado | delegada |
| C. Visibilidade da degradação | O que o vendedor vê quando o LLM falha | ✓ |
| D. Injeção de prompt e teste | Quanto da mitigação da §11 entra hoje, e quanto teste | delegada |

---

## A. Provedor e saída estruturada

### A1 — Como o LLMExtractor fala com o modelo?

| Option | Description | Selected |
|--------|-------------|----------|
| httpx direto | Zero dependência nova — httpx já está no requirements.txt. Sem pip install antes da demo, serve qualquer provedor compatível com OpenAI | ✓ |
| SDK openai | Retry e parsing tipado prontos, mas amarra ao provedor e exige instalar hoje | |
| Você decide | Claude escolhe pelo menor risco | |

**User's choice:** httpx direto
**Notes:** Recomendação do Claude, baseada em leitura do disco — `httpx` já era
dependência via `fetcher.py:46`. O fato de a chave ainda não ter chegado (provedor
desconhecido) pesou: endpoint compatível com OpenAI aceita chave de OpenAI, Azure,
Groq, OpenRouter ou vLLM local sem mudança de código.

### A2 — Como garantir o formato do JSON?

| Option | Description | Selected |
|--------|-------------|----------|
| json_schema nativo + Pydantic | response_format derivado de Briefing.model_json_schema(), mais validação na volta | ✓ |
| JSON pedido no prompt + Pydantic | Funciona em qualquer provedor, erra formato com mais frequência | |
| Você decide | Claude escolhe | |

**User's choice:** json_schema nativo + Pydantic
**Notes:** Degradação para o modo prompt-only registrada como comportamento esperado
caso o provedor não suporte `json_schema`.

### A3 — Timeout e retry?

| Option | Description | Selected |
|--------|-------------|----------|
| Timeout 20s, sem retry | O fallback heurístico já é a recuperação; retry dobra a espera para o mesmo resultado | ✓ |
| Timeout 20s + 1 retry | Briefing melhor com mais frequência, até 40s por URL no pior caso | |
| Você decide | Claude escolhe | |

**User's choice:** Timeout 20s, sem retry
**Notes:** Com o limite de 10 URLs por requisição (RF1), retry poderia estender uma
demonstração ao vivo por minutos.

### A4 — Onde ficam os parâmetros?

| Option | Description | Selected |
|--------|-------------|----------|
| config.py só com o do LLM | LLM_API_KEY, LLM_MODELO, LLM_MAX_CHARS + .env.example. Não toca fetcher.py nem db.py | ✓ |
| config.py com as 8 variáveis | Fecha a §13 por inteiro, mas toca módulos estáveis e testados | |
| Manter os.getenv inline | Menor mudança, mantém a divergência e o hardcode | |

**User's choice:** config.py só com o do LLM
**Notes:** Divergência da §13 fechada parcialmente (3 de 8 variáveis). As outras 5
foram para deferred.

---

## C. Visibilidade da degradação

### C1 — O que o campo `extrator` mostra no fallback?

| Option | Description | Selected |
|--------|-------------|----------|
| Campo separado de aviso | extrator continua "heuristico"; campo opcional novo em BriefingResponse marca a degradação | ✓ |
| extrator = "heuristico (fallback)" | Uma linha, mas inventa quarto valor fora da §8 e suja a coluna do banco | |
| Manter "heuristico" puro | Sem mudança de schema; degradação fica invisível na tela | |

**User's choice:** Campo separado de aviso
**Notes:** Contexto que motivou a pergunta: hoje um fallback do LLM e uma execução sem
chave produzem exatamente o mesmo `heuristico`, indistinguíveis em `index.html:95`.

### C2 — O motivo da falha chega ao vendedor?

| Option | Description | Selected |
|--------|-------------|----------|
| Sim, curto e sem stack trace | Mesmo padrão do FetchError em main.py:78 | ✓ |
| Só no log do servidor | Tela mais limpa, usuário menos informado | |
| Você decide | Claude escolhe | |

**User's choice:** Sim, curto e sem stack trace

### C3 — A UI destaca o briefing degradado?

| Option | Description | Selected |
|--------|-------------|----------|
| Tag de aviso no cartão | Reaproveita a classe .tag existente com cor de atenção, ~6 linhas | ✓ |
| Só texto, sem destaque | Menos código, passa despercebido na apresentação | |
| Você decide | Claude escolhe | |

**User's choice:** Tag de aviso no cartão
**Notes:** Custo marginal baixo porque `static/index.html` já seria tocado pela correção
do mojibake.

### C4 — Dá para saber o extrator ativo sem gerar briefing?

| Option | Description | Selected |
|--------|-------------|----------|
| /health mostra o extrator ativo | Conferência instantânea antes da demo, ~2 linhas. Extensão aditiva do contrato da §10 | ✓ |
| Endpoint novo separado | Mais fiel à §10, mais uma rota para documentar | |
| Nada disso hoje | Confere gerando briefing de teste | |

**User's choice:** /health mostra o extrator ativo
**Notes:** A ressalva de que a §10 define `/health` como `{"status":"ok"}` foi
apresentada junto com a opção, não depois. Mudança é aditiva.

---

## Claude's Discretion

Nenhuma pergunta individual foi respondida com "você decide". Duas áreas inteiras foram
delegadas na seleção inicial:

**B. Cache × troca de extrator** → D-09, D-10
- Regra de upgrade de extrator no `buscar()`: entrada `heuristico` vira miss quando o
  LLM está disponível.
- `conteudo_hash` (§8) adiado: `briefings.db` já tem dados, `CREATE TABLE IF NOT EXISTS`
  não adiciona coluna, e o campo resolve outro problema (página mudou) que não é o da
  demonstração (extrator melhorou).
- Alternativas descartadas: limpar o banco antes da demo (volta a acontecer na segunda
  demonstração, e o cache cheio é o que prova o Bônus 1); demonstrar com "Ignorar cache"
  marcado (esconde o problema em vez de resolver).

**D. Injeção de prompt e teste** → D-11, D-12
- Mitigação de injeção implementada por completo: é redação de prompt, não arquitetura.
- Quatro testes sem chave e sem rede, no `test_smoke.py` existente.
- `tests/` em quatro arquivos (§12) adiado: churn sem valor de demonstração.

---

## Escopo cortado, declarado ao usuário

Apresentado antes da gravação do CONTEXT.md, conforme pedido explícito
("se o plano não couber no tempo, corte escopo e me diga o que cortou"):

`conteudo_hash` (§8) · `config.py` com as 8 variáveis (§13, entram 3) · `tests/` em 4
arquivos (§12) · `README.md`, `AI-LOG.md`, `Dockerfile`, `docker-compose.yml` (Fase 7) ·
exportar briefing (§4 item 8) · conjunto de avaliação de prompt (§11, precisa de chave).

## Deferred Ideas

Ver `<deferred>` em `05-CONTEXT.md` para a lista completa com justificativa.

## Desvio de processo registrado

`init.phase-op 5` retornou `phase_found: false` e `roadmap_exists: false` — não existe
`.planning/`. O workflow padrão manda encerrar e rodar `/gsd-new-project` primeiro. O
Claude sinalizou isso ao usuário e prosseguiu usando `SPEC-sales-intel.md` §15 como
roadmap efetivo, por causa da restrição de prazo (apresentação às 17h). Scaffolding GSD
completo registrado em deferred.
