# Sales Intel — Especificação do Projeto

Case bna.dev. Documento de referência para o projeto e para a execução por fases.

---

## 1. Contexto

A bna.dev é uma fábrica de software focada em infraestrutura para sistemas com IA: automações, análise de dados e documentos, e chatbots para SDR e vendas. As soluções rodam nos servidores dos clientes. O lema declarado é 80% IA, 20% humano.

O desafio pedido: uma equipe de vendas precisa automatizar a coleta de informações relevantes na web antes de uma reunião de apresentação para um cliente específico.

## 2. O problema real

O enunciado fala em "coletar informações através da web", o que parece pedir um scraper. Não é.

O vendedor não quer o texto do site. Ele quer entrar na reunião sabendo o que a empresa faz, qual o porte, o que aconteceu de novo por lá, quem provavelmente decide, qual dor ele pode atacar, e com que frase abrir a conversa.

**O produto é um briefing de reunião. O scraping é meio, não fim.**

Consequência de projeto: o artefato central é o schema do briefing, não o extrator de HTML.

## 3. Usuário e job-to-be-done

Usuário primário: vendedor ou SDR, sem perfil técnico, com pouco tempo antes da call.

Job: "Tenho reunião com a empresa X em 30 minutos. Me dá o que eu preciso saber."

Fluxo mental dele: cola link → espera poucos segundos → lê uma tela → entra na reunião.

Implicações diretas:
- A tela precisa ser legível em uma passada, sem rolagem infinita.
- Resultado parcial é melhor que erro. Se três links funcionam e um falha, mostra os três.
- Precisa dizer o quanto confia no que entregou. Briefing errado com cara de certo é pior que briefing vazio.

## 4. Escopo

### Entra no MVP
1. API que recebe uma lista de links e devolve um briefing estruturado por link.
2. Cache em banco: link já processado não é raspado de novo (Bônus 1 do case).
3. UI web onde o vendedor cola links e lê os briefings.
4. Extração com LLM produzindo saída estruturada validada por schema.
5. Extrator heurístico como fallback, sem custo e sem dependência de API.

### Entra se sobrar tempo
6. Autenticação e área de admin na UI (Bônus 2 do case).
7. Histórico consultável de briefings gerados.
8. Exportar briefing como texto para colar no CRM ou no WhatsApp.

### Fica de fora, e é decisão consciente
- Crawling de site inteiro. O usuário informa as páginas relevantes.
- Busca automática de notícias em fontes externas.
- Integração com CRM.
- Renderização de JavaScript (sites SPA). Registrado como limitação conhecida.

Declarar os cortes na apresentação, com o motivo. Corte explícito lê como escopo controlado; corte silencioso lê como esquecimento.

## 5. Requisitos funcionais

| # | Requisito |
|---|---|
| RF1 | Aceitar de 1 a 10 URLs por requisição |
| RF2 | Validar formato de URL e rejeitar entrada inválida com mensagem clara |
| RF3 | Consultar o cache antes de buscar; devolver o registro salvo se estiver válido |
| RF4 | Permitir forçar atualização, ignorando o cache |
| RF5 | Buscar o HTML com timeout e limite de tamanho |
| RF6 | Extrair texto legível descartando script, estilo e navegação |
| RF7 | Gerar briefing estruturado conforme o schema definido |
| RF8 | Persistir o briefing em JSON, indexado pela URL |
| RF9 | Falha em uma URL não interrompe as demais |
| RF10 | Expor endpoint de histórico dos briefings gerados |
| RF11 | UI: colar links, disparar coleta, ver estado de carregamento, ler resultado |
| RF12 | UI: indicar visualmente se veio do cache ou foi coletado agora |
| RF13 | Endpoint `/health` para verificação de saúde |

## 6. Requisitos não funcionais

**Resiliência.** Site fora do ar, timeout, resposta que não é HTML, LLM indisponível: nenhum desses casos pode derrubar a requisição inteira. Cada um vira um resultado de confiança baixa com o motivo explicado.

**Custo e latência.** Chamada de LLM custa dinheiro e tempo. Mitigações: cache é a primeira linha, texto enviado ao modelo tem corte máximo de caracteres, e o modelo default é o mais barato que resolve.

**Ética de coleta.** A bna instala nas máquinas dos clientes, então raspagem irresponsável vira problema jurídico do cliente. Obrigatório: consultar robots.txt, enviar user-agent identificável com contato, respeitar timeout, não paralelizar contra o mesmo domínio.

**Segurança.** Chave de API só em variável de ambiente, nunca no código. Nenhum segredo no repositório. Se houver autenticação, senha com hash forte e papel validado no servidor a cada requisição, nunca só escondendo botão na tela.

**Portabilidade.** Roda com um comando em máquina limpa. Docker Compose para produção.

## 7. Arquitetura

```
Vendedor
   |
   v
UI (React ou HTML servido pela API)
   |  POST /api/briefings  { urls: [...] }
   v
FastAPI
   |
   +--> Cache (banco)  -- achou e está válido? --> devolve
   |
   +--> Fetcher      -- robots.txt, GET, limite de tamanho
   |        |
   |        v
   |    Extrator de texto (função pura, sem rede)
   |        |
   |        v
   +--> Extractor (interface)
   |        |-- LLMExtractor       (usa quando há chave)
   |        `-- HeuristicExtractor (fallback, sem custo)
   |
   +--> valida contra o schema Briefing
   |
   `--> persiste JSON no banco --> devolve ao vendedor
```

### A decisão central: extrator atrás de interface

Existe um contrato `Extractor` com um método `extrair(url, titulo, texto) -> Briefing`. Duas implementações o cumprem. Quem chama não sabe qual está rodando.

Isso resolve quatro problemas de uma vez:
1. O sistema funciona antes de existir chave de API.
2. Se o LLM cair ou o orçamento estourar, existe para onde degradar.
3. Dá para comparar as duas saídas e medir se o LLM de fato melhora o resultado.
4. Trocar de provedor (OpenAI, Gemini, Llama) mexe em um arquivo só.

Esse é o ponto mais forte da apresentação. Ele demonstra decisão de arquitetura, não só entrega de feature.

### Separação de responsabilidades

| Módulo | Responsabilidade | Testável sem rede? |
|---|---|---|
| `schemas.py` | Formato dos dados de entrada e saída | sim |
| `fetcher.py` | Buscar HTML e extrair texto limpo | a extração sim, a busca não |
| `extractor.py` | Texto → Briefing estruturado | o heurístico sim |
| `db.py` | Cache e histórico | sim |
| `main.py` | Rotas e orquestração do fluxo | sim, com cliente de teste |

## 8. Modelo de dados

### Tabela `briefings`

| Coluna | Tipo | Observação |
|---|---|---|
| `url` | texto, chave primária | URL normalizada |
| `briefing` | JSON | O briefing serializado |
| `extrator` | texto | `llm`, `heuristico` ou `falha` |
| `conteudo_hash` | texto | Hash do texto extraído, detecta mudança de página |
| `coletado_em` | timestamp | Base para calcular validade |
| `owner` | texto, nulo | id do usuário que gerou o briefing (Fase 6); nulo em linha anterior à Fase 6 |

Validade padrão do cache: 7 dias. Passado isso, considera desatualizado e raspa de novo.

**Política de leitura de `owner` (D-18).** O filtro de visibilidade vive na leitura, não numa migração: vendedor vê apenas as próprias linhas, admin vê todas, e linha sem dono (anterior à Fase 6) é visível apenas para admin. Nenhuma migração reescreve ou remove linha existente.

**`conteudo_hash` especificado e não implementado.** A coluna está na tabela desde a Fase 0, mas nenhum código grava ou lê valor nela — risco aceito R-10 da Fase 5 (`05-SECURITY.md`), que adiou a revalidação de conteúdo em cache. Um leitor novo desta seção pode supor, pela presença da coluna, que ela é usada; não é.

### Tabela `usuarios`

| Coluna | Tipo |
|---|---|
| `id` | uuid |
| `username` | texto, único |
| `senha_hash` | texto, formato autodescritivo `scrypt$n$r$p$salt$chave` (`n`, `r`, `p` em texto puro; `salt` e `chave` derivada em base64) |
| `papel` | `vendedor` ou `admin` |
| `ativo` | booleano |
| `criado_em` | timestamp |

**Divergência registrada (D-15).** A versão anterior deste documento definia `senha_hash` como `texto (argon2)`. A decisão travada D-15 escolheu `hashlib.scrypt` da biblioteca padrão em vez de argon2: `argon2-cffi` é pacote novo com extensão C compilada, e L-06 proíbe instalar dependência nova antes da entrega. Os parâmetros de custo (`n`, `r`, `p`) ficam gravados dentro da própria string de hash, para que um aumento futuro de custo não invalide hash já gravado. A comparação na verificação é feita em tempo constante (`hmac.compare_digest`), nunca com `==`.

### Tabela `sessoes`

| Coluna | Tipo |
|---|---|
| `token_hash` | texto, chave primária |
| `usuario_id` | texto |
| `criada_em` | timestamp |
| `expira_em` | timestamp |

**Sessão (D-16).** `token_hash` é o sha256 do token de sessão; o token bruto vive apenas no cookie do navegador, nunca no banco. Sessão é token opaco de 32 bytes gerado por CSPRNG (`secrets.token_urlsafe`), não JWT nem cookie assinado à mão. Revogação é remoção de linha. Duração de 12 horas.

## 9. Schema do Briefing

Este é o artefato central. Cada campo existe porque responde uma pergunta que o vendedor faz.

| Campo | Tipo | Pergunta que responde |
|---|---|---|
| `empresa` | texto | Com quem eu vou falar? |
| `resumo` | texto (2-3 frases) | O que essa empresa faz? |
| `segmento` | texto, opcional | Em que setor ela atua? |
| `porte_estimado` | texto, opcional | É startup, média ou grande? |
| `produtos` | lista | O que ela vende? |
| `publico_alvo` | texto, opcional | Para quem ela vende? |
| `sinais_recentes` | lista | O que mudou por lá? Gancho de abertura. |
| `dores_provaveis` | lista | Que problema nosso produto resolve para ela? |
| `ganchos_de_conversa` | lista | Como eu começo a conversa? |
| `contatos` | lista | E-mails e telefones públicos encontrados |
| `confianca` | alta / média / baixa | O quanto dá para confiar nisso? |

O campo `confianca` não é enfeite. Ele é o que impede o vendedor de entrar numa reunião confiando em alucinação. Extrator heurístico sempre devolve baixa, porque ele de fato não entende o conteúdo.

## 10. Contrato da API

### `POST /api/briefings`

Entrada:
```json
{ "urls": ["https://exemplo.com.br"], "forcar_atualizacao": false }
```

Saída: lista de objetos com `url`, `briefing`, `origem` (`cache` ou `novo`), `extrator`, `coletado_em`.

Erros: 422 para entrada inválida. Falha por URL não vira erro HTTP, vira briefing de confiança baixa com o motivo no campo `resumo`.

### `GET /api/historico?limite=50`
Lista de briefings gerados, mais recentes primeiro.

### `GET /health`
`{"status": "ok"}`

### Inventário de rotas (Bônus 2)

| Rota | Quem pode chamar | Guarda |
|---|---|---|
| `GET /health` | público | nenhuma; requisito funcional RF13, devolve apenas booleanos |
| `GET /` | público | nenhuma; é a própria tela de login |
| `GET /static/*` | público | nenhuma; ativos da UI, sem dado de negócio |
| `POST /api/auth/login` | público | limite por IP e por username; única porta que aceita credencial |
| `POST /api/auth/logout` | autenticado | `usuario_atual` |
| `GET /api/auth/me` | autenticado | `usuario_atual` |
| `POST /api/briefings` | autenticado | `usuario_atual` mais o limite por IP já existente |
| `GET /api/historico` | autenticado | `usuario_atual`; vendedor vê apenas as próprias linhas, admin vê todas |
| `GET /api/admin/usuarios` | somente admin | `exigir_admin` |
| `POST /api/admin/usuarios` | somente admin | `exigir_admin` |
| `POST /api/admin/usuarios/{usuario_id}/ativo` | somente admin | `exigir_admin` |

**Erros de autorização.** 401 quando não há sessão válida; 403 quando há sessão mas o papel não basta. Dois estados distintos, ambos avaliados no servidor, ambos com mensagem autorada e genérica.

**Regra de D-17 e L-07.** A autorização é avaliada no servidor a cada requisição, por dependência declarada na rota. Esconder um botão na interface não é controle de acesso. Uma rota nova sem linha nesta tabela é um defeito, e existe um teste de inventário (plano 06-04) que quebra quando isso acontece.

**Por que `/health` continua público.** Requisito funcional RF13, devolve somente booleanos e nenhum dado de negócio; o risco aceito R-08 da Fase 5 fica renovado nesta fase, não revogado.

**Configuração não entra pela interface.** Nenhuma rota lê ou grava variável de configuração do processo; a área de administração é apenas leitura sobre histórico e usuários, mais criação e ativação de usuário. Consequência declarada: o risco aceito R-11 da Fase 5 segue válido mesmo com a fronteira operador/usuário passando a existir, porque o administrador do produto não ganhou poder sobre a configuração do processo.

## 11. Estratégia de extração com LLM

**Saída estruturada obrigatória.** O modelo devolve JSON no formato do schema, validado pelo Pydantic. Se vier fora do formato, levanta erro em vez de entregar lixo para o vendedor.

**O prompt precisa cobrir:**
- Papel: analista preparando briefing comercial.
- Instrução explícita de não inventar. Campo sem base no texto fica vazio.
- Regra do campo `confianca`: baixa quando o texto tem pouco conteúdo útil.
- Formato de saída, com o schema declarado.

**Limite de entrada.** Corte em torno de 12 mil caracteres. Texto mais longo não melhora o resultado e multiplica o custo por chamada.

**Injeção de prompt é risco real aqui.** O texto vem de site de terceiro, e uma página pode conter instrução escondida tentando redirecionar o modelo. Mitigações: separar claramente instrução de conteúdo, tratar a página como dado e nunca como comando, e validar a saída pelo schema antes de usar.

**Avaliação.** Montar um conjunto pequeno de páginas com o resultado esperado, e rodar contra ele ao mudar o prompt. Sem isso, "melhorei o prompt" é opinião.

## 12. Estrutura de pastas

```
sales-intel/
├── app/
│   ├── __init__.py
│   ├── main.py           # rotas e orquestração
│   ├── schemas.py        # Briefing e contratos de entrada/saída
│   ├── fetcher.py        # busca HTML, extrai texto, respeita robots
│   ├── extractor.py      # interface + heurístico + LLM
│   ├── db.py             # cache e histórico
│   ├── config.py         # variáveis de ambiente
│   └── auth.py           # só se o bônus 2 entrar
├── static/
│   └── index.html        # UI
├── tests/
│   ├── test_fetcher.py
│   ├── test_extractor.py
│   ├── test_cache.py
│   └── test_api.py
├── .env.example
├── .gitignore
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── README.md
└── AI-LOG.md             # registro de como a IA foi usada
```

## 13. Variáveis de ambiente

```
LLM_API_KEY=              # vazio: cai no extrator heurístico
LLM_MODELO=gpt-4o-mini
LLM_MAX_CHARS=12000
DATABASE_URL=sqlite:///./briefings.db
CACHE_VALIDADE_DIAS=7
FETCH_TIMEOUT=15
USER_AGENT=bna-sales-intel/0.1 (+contato: gabriel@bna.dev.br)
DEBUG=false
ADMIN_USERNAME=
ADMIN_SENHA=
```

As duas variáveis acima semeiam o primeiro administrador na subida do processo (D-19): não existe cadastro público, e o sistema nunca traz credencial embutida no código — sem as duas, nenhum administrador é criado.

## 14. Testes

| Arquivo | O que cobre |
|---|---|
| `test_fetcher.py` | Extração de texto de HTML fixo: remove script e menu, preserva rodapé, pega título |
| `test_extractor.py` | Heurístico monta briefing e encontra contatos; LLM sem chave levanta erro claro |
| `test_cache.py` | Salva e busca; registro vencido não é devolvido; atualização sobrescreve |
| `test_api.py` | Caminho feliz, entrada inválida vira 422, uma URL falhando não derruba as outras |

Regra: se o teste precisa de internet para passar, ele está mal escrito. Rede se isola com HTML fixo.

Detalhe já descoberto e que vale manter coberto: remover a tag `<footer>` na limpeza do HTML apaga e-mail e telefone, que é justamente o dado mais acionável. O rodapé fica.

## 15. Fases de entrega

Cada fase termina em algo que roda e é verificável.

**Fase 0 — Base**
Estrutura de pastas, dependências, `/health` respondendo, primeiro teste passando, repositório com commit inicial.
Pronto quando: `pytest` verde e `/health` devolve ok.

**Fase 1 — Coleta e extração de texto**
Fetcher com robots.txt, timeout e limite de tamanho. Extração de texto pura, testada com HTML fixo.
Pronto quando: dada uma página, sai título e texto limpo, com teste sem rede.

**Fase 2 — Briefing heurístico**
Schema completo, interface `Extractor`, implementação heurística.
Pronto quando: uma URL real vira um Briefing válido, sem nenhuma chave de API.

**Fase 3 — Cache**
Tabela, gravação, leitura, validade, forçar atualização.
Pronto quando: a segunda chamada da mesma URL volta marcada como `cache` e não bate no site.

**Fase 4 — UI**
Tela de colar links, estado de carregamento, cartões de resultado, indicação de origem e confiança.
Pronto quando: o fluxo inteiro funciona pelo navegador, sem usar curl.

**Fase 5 — LLM**
`LLMExtractor` ligado, saída estruturada validada, seleção automática entre LLM e heurístico, tratamento de erro e limite de caracteres.
Pronto quando: com chave, o briefing vem rico; sem chave, cai no heurístico sem quebrar.

**Fase 6 — Bônus: autenticação e admin**
Login, papéis, proteção das rotas no servidor, tela de admin com histórico.
Pronto quando: vendedor não acessa rota de admin nem chamando a API direto.

**Fase 7 — Empacotamento**
Dockerfile, compose, README que roda em máquina limpa, AI-LOG preenchido.
Pronto quando: alguém clona o repositório e sobe com um comando.

## 16. Riscos e limitações conhecidas

| Risco | Situação |
|---|---|
| Site em JavaScript puro devolve HTML vazio | Limitação declarada. Solução seria navegador headless, fora do escopo. |
| Custo de LLM cresce com o uso | Mitigado por cache e corte de texto. |
| Alucinação do modelo | Mitigado por saída estruturada, instrução de não inventar e campo de confiança. |
| Injeção de prompt via conteúdo da página | Mitigado por separação entre instrução e dado, e validação da saída. |
| Bloqueio por parte do site | robots.txt respeitado, user-agent identificado, sem paralelismo no mesmo domínio. |
| Cache servindo dado velho | Validade de 7 dias e opção de forçar atualização. |

## 17. Definição de pronto

- Sobe em máquina limpa seguindo o README, sem passo escondido.
- `pytest` todo verde.
- Nenhum segredo no repositório; existe `.env.example`.
- README explica o que faz, como rodar, decisões tomadas, o que ficou de fora e por quê, e como a IA foi usada.
- Commits pequenos, com mensagem no padrão `feat:`, `fix:`, `test:`, `docs:`, `chore:`.
- `AI-LOG.md` preenchido durante o trabalho, não reconstruído no final.

## 18. Registro de uso de IA

Manter `AI-LOG.md` desde o primeiro minuto, uma entrada por tarefa:

```
## [tarefa]
Contexto: o que eu precisava
Como pedi: resumo do pedido
O que voltou: útil / parcial / errado
O que eu mudei:
Por que aceitei ou rejeitei:
```

Guardar obrigatoriamente: um caso em que a IA errou e foi corrigida, e um caso em que a decisão foi deliberadamente não usar IA.

Isso não é burocracia. O case pede explicitamente "como IA foi usada durante o processo ou para a solução em si", e a bna vive de implantar IA em empresa. O processo é parte do que está sendo avaliado.
