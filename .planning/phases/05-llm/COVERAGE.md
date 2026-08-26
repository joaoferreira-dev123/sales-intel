# Phase 5 — Cobertura da API externa

**Gerado:** 2026-08-26
**Atualizado:** 2026-08-26 (chave recebida — provedor conhecido; D-13, D-14)

**API externa:** **Groq**, endpoint de *chat completions* compativel com a API da OpenAI
(`https://api.groq.com/openai/v1`), chamado por `httpx` direto (D-01). A escolha de D-01 —
`httpx` em vez de SDK — se pagou aqui: o provedor mudou entre o planejamento e a execucao e
nenhuma linha de codigo de chamada precisou mudar.

**Modelo:** `openai/gpt-oss-120b`, fixado como **padrao no codigo por D-13 invertida** e escolhido
por ser o **unico modelo grande da conta com suporte a `structured_outputs`** — os demais so
oferecem `json_mode` (motivo tecnico registrado em D-14). Essa e exatamente a capacidade que o
caminho primario de D-02 exige, entao a escolha de modelo trava junto com a decisao: trocar
`LLM_MODELO` por outro modelo da conta cai no galho de degradacao de D-02, e nao no caminho
principal.

> **Nota:** o detector deterministico de api-coverage devolveu `detected: false` para esta fase.
> E falso negativo: o vocabulario de gatilho do detector e em ingles e o escopo desta fase esta
> escrito em portugues. Esta fase **integra** uma API externa. Esta matriz existe para que isso
> fique registrado, e nao para virar documento grande.

## Superficie em uso

| Capacidade | Uso nesta fase | Onde |
|---|---|---|
| `POST /chat/completions` | **USADA** — uma chamada por URL, sincrona | `LLMExtractor._chamar_provedor` |
| Endereco base do endpoint | **USADA** — vem de `config.LLM_BASE_URL`; padrao e valor em uso sao o mesmo `https://api.groq.com/openai/v1` (D-13 invertida) | `app/config.py` |
| `model` | **USADA** — vem de `config.LLM_MODELO`; padrao e valor em uso sao o mesmo `openai/gpt-oss-120b`, divergindo da SPEC §13 de proposito (D-13 invertida; motivo tecnico da escolha em D-14) | `app/config.py` |
| `messages` (papeis `system` + `user`) | **USADA** — instrucao e dado em mensagens separadas (D-11) | `LLMExtractor._montar_mensagens` |
| `response_format: json_schema` (`structured_outputs`) | **USADA — caminho primario, verificado contra modelo real** — schema derivado de `Briefing.model_json_schema()` (D-02); e a capacidade pela qual `gpt-oss-120b` foi escolhido (D-14) | `LLMExtractor._chamar_provedor` |
| `response_format` ausente (JSON pedido no prompt) | **USADA — galho de degradacao, coberto so por duplo** — D-02, disparado por HTTP 400 citando `response_format`. `gpt-oss-120b` nao produz esse 400, entao a verificacao com modelo real **nao** exercita este caminho (D-14) | `LLMExtractor.extrair` |
| `temperature` | **USADA** — fixada em `0`, para reduzir variacao entre execucoes | `LLMExtractor._chamar_provedor` |
| `Authorization: Bearer` | **USADA** — unica forma de autenticacao; chave so por variavel de ambiente (SPEC §6) | `LLMExtractor._chamar_provedor` |

## Fora de uso, com motivo

| Capacidade | Status | Motivo |
|---|---|---|
| `strict: true` no `json_schema` | **OPT-OUT** | exigiria `additionalProperties: false` e todos os campos em `required`, que `Briefing.model_json_schema()` nao produz; a garantia real e `Briefing(**dados)` na volta (D-02, L-03) |
| `stream: true` | **OPT-OUT** | a UI mostra o cartao pronto, nao token a token; streaming nao encurta o tempo ate o vendedor poder ler |
| `tools` / `function calling` | **OPT-OUT** | o modelo nao recebe nenhuma ferramenta de proposito — reduz a superficie de injecao de prompt (D-11, ameaca T-05-29) |
| Retry / backoff do provedor | **OPT-OUT** | D-03: sem retry; o fallback heuristico ja e a estrategia de recuperacao |
| Batch API / requisicoes assincronas | **OPT-OUT** | o vendedor espera segundos, nao minutos; o fluxo e sincrono por desenho (SPEC §3) |
| Embeddings, moderacao, arquivos, assistentes | **OPT-OUT** | fora do escopo do produto (SPEC §4) |
| `max_tokens`, `top_p`, `seed`, penalidades | **OPT-OUT** | knob sem retorno de demonstracao; o controle de custo que importa e o corte de entrada de L-04 |
| SDK oficial do provedor | **OPT-OUT** | D-01: `httpx` direto evita pacote novo antes da demo e serve qualquer endpoint compativel (L-06). Confirmado na pratica quando o provedor virou Groq |
| `json_mode` (`response_format: {"type": "json_object"}`) | **OPT-OUT** | os outros modelos grandes da conta so oferecem isto; `gpt-oss-120b` foi escolhido justamente para usar `structured_outputs` (D-14). O sistema ainda degrada para JSON pedido no prompt se algum dia rodar contra modelo sem schema nativo |

## Limitacao registrada

**Verificacao contra provedor real:** a chave chegou antes da execucao (D-13/D-14). A Task 4 do
`05-05-PLAN.md` roda 2 ou 3 URLs reais contra `openai/gpt-oss-120b` no endpoint do Groq — a
verdade *"com chave, o briefing vem rico"* deixou de ser `verification: backstop` e virou verdade
explicita nos `must_haves` de `05-05`.

**O que essa verificacao ainda nao cobre:** apenas o caminho primario de D-02 e exercitado. O
galho de degradacao (`response_format` ausente) so dispara em HTTP 400, que `gpt-oss-120b` nao
produz, e segue coberto somente por teste com duplo. "LLM verificado" nao e o mesmo que "os dois
caminhos de D-02 verificados".

**Armadilha operacional (D-13), fechada por construcao:** o desenho anterior deixava o padrao de
`LLM_BASE_URL` apontando para a OpenAI enquanto a chave real e do Groq — exportar `LLM_API_KEY`
sozinha mandava a chave para o provedor errado, tomava 401 e degradava em silencio para o
heuristico. **O usuario inverteu os dois padroes**, endpoint e modelo juntos, e a armadilha deixou
de existir no caminho padrao: so `LLM_API_KEY` precisa ser configurada. Inverter apenas o endpoint
teria movido a falha de porta, porque `gpt-4o-mini` nao existe no Groq e daria 400/404 com a mesma
degradacao silenciosa. **Residual invertido, muito menor:** quem tiver chave da *OpenAI* e nao
definir nenhuma das duas variaveis manda essa chave para o Groq e toma 401 — caso improvavel,
porque nao existe chave da OpenAI neste projeto, e ainda visivel pelo `.env.example` e pela
mensagem de degradacao que chega ao vendedor (D-06/D-07).
