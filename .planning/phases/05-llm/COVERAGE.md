# Phase 5 — Cobertura da API externa

**Gerado:** 2026-08-26
**API externa:** endpoint de *chat completions* compativel com OpenAI, chamado por `httpx`
direto (D-01). Provedor concreto ainda desconhecido — a chave nao chegou.

> **Nota:** o detector deterministico de api-coverage devolveu `detected: false` para esta fase.
> E falso negativo: o vocabulario de gatilho do detector e em ingles e o escopo desta fase esta
> escrito em portugues. Esta fase **integra** uma API externa. Esta matriz existe para que isso
> fique registrado, e nao para virar documento grande.

## Superficie em uso

| Capacidade | Uso nesta fase | Onde |
|---|---|---|
| `POST /chat/completions` | **USADA** — uma chamada por URL, sincrona | `LLMExtractor._chamar_provedor` |
| `model` | **USADA** — vem de `config.LLM_MODELO`, padrao `gpt-4o-mini` (SPEC §13) | `app/config.py` |
| `messages` (papeis `system` + `user`) | **USADA** — instrucao e dado em mensagens separadas (D-11) | `LLMExtractor._montar_mensagens` |
| `response_format: json_schema` | **USADA** — schema derivado de `Briefing.model_json_schema()` (D-02) | `LLMExtractor._chamar_provedor` |
| `response_format` ausente (JSON pedido no prompt) | **USADA** — caminho de degradacao de D-02, disparado por HTTP 400 citando `response_format` | `LLMExtractor.extrair` |
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
| SDK oficial do provedor | **OPT-OUT** | D-01: `httpx` direto evita pacote novo antes da demo e serve qualquer endpoint compativel (L-06) |
| `LLM_BASE_URL` configuravel por ambiente | **OPT-OUT** | D-04 trava `config.py` em tres variaveis; o endpoint e constante de modulo em `app/extractor.py`, preservando "um arquivo so" da SPEC §7 item 4 |

## Limitacao registrada

Nada nesta matriz foi exercitado contra um provedor real: **nao existe chave de API nesta fase**.
Ver a verdade marcada `verification: backstop` em `05-05-PLAN.md`.
