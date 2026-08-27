# Sales Intel

Briefing de cliente a partir de links, para equipe de vendas.

O vendedor cola as URLs do cliente antes da reunião e recebe uma ficha estruturada: o que a empresa faz, produtos, dores prováveis e ganchos de conversa prontos para usar.

---

## O problema

Uma equipe de vendas precisa se preparar antes de entrar numa reunião com um cliente, e ninguém tem tempo de ler o site inteiro da empresa procurando o que importa.

O enunciado fala em coletar informações através da web, o que parece pedir um scraper. Mas o vendedor não quer o texto do site: ele quer saber o que a empresa faz, qual dor ele pode atacar e com que frase abrir a conversa.

Por isso o produto aqui é o briefing pronto para a reunião. O scraping é meio, não fim.

---

## Como rodar

Requer Python 3.12.

```bash
git clone https://github.com/joaoferreira-dev123/sales-intel.git
cd sales-intel

python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env      # preencha LLM_API_KEY, ADMIN_USERNAME e ADMIN_SENHA
uvicorn app.main:app
```

Abra `http://127.0.0.1:8000` e entre com o usuário e a senha definidos em `ADMIN_USERNAME` / `ADMIN_SENHA`.

**Sem chave de API o sistema roda igual**, usando o extrator por regras em vez do LLM. O briefing sai mais pobre e a resposta vem marcada como degradada, mas nada quebra.

Testes:

```bash
pytest -q
```

Todos offline: nenhum depende de rede ou de chave de API.

---

## Como funciona

```
Vendedor cola URLs
        │
        ▼
POST /api/briefings
        │
        ├── cache válido? ──► devolve o JSON salvo
        │
        ├── busca a página (robots.txt, timeout, limite de tamanho, validação de URL)
        │
        ├── extrai o texto legível do HTML
        │
        ├── Extractor ──┬── LLMExtractor       (quando há chave)
        │               └── HeuristicExtractor (fallback, sem custo)
        │
        ├── valida contra o schema Briefing
        │
        └── salva no cache e devolve
```

### Rotas

| Rota | Quem acessa | O que faz |
|---|---|---|
| `GET /` | público | A interface: tela de login ou painel, conforme a sessão |
| `GET /health` | público | Saúde do serviço e qual extrator está ativo |
| `POST /api/auth/login` | público | Autentica e cria a sessão |
| `POST /api/auth/logout` | autenticado | Encerra a sessão |
| `GET /api/auth/me` | autenticado | Quem está logado e qual o papel |
| `POST /api/briefings` | autenticado | Recebe até 10 URLs, devolve um briefing por URL |
| `GET /api/historico` | autenticado | Briefings gerados. Vendedor vê os seus, admin vê todos |
| `GET /api/admin/usuarios` | admin | Lista de usuários |
| `POST /api/admin/usuarios` | admin | Cria usuário |
| `POST /api/admin/usuarios/{id}/ativo` | admin | Ativa ou desativa usuário |

---

## Decisões técnicas

### O extrator fica atrás de uma interface

Existe um contrato com um método `extrair`, e duas implementações o cumprem: uma com LLM e uma por regras. Quem chama não sabe qual está rodando.

Isso resolve quatro coisas de uma vez: o sistema funciona antes de existir chave de API, existe para onde degradar se o LLM cair ou o custo estourar, dá para comparar as duas saídas, e trocar de provedor mexe em um arquivo só.

### Saída estruturada em duas camadas

O schema vai junto no pedido ao modelo, derivado do próprio modelo de dados, então o provedor força o formato. E a resposta é validada de novo na volta. Se uma camada falhar, a outra segura.

Como o schema é derivado e não escrito à mão, adicionar campo novo não exige lembrar de atualizar dois lugares.

### Sem retry

A recuperação já existe: é a degradação para o extrator por regras. Retry seria uma segunda rede para proteger a primeira, e o preço é o vendedor esperando o dobro para receber, no pior caso, o mesmo resultado.

O produto é preparo de reunião. O vendedor tem trinta minutos até a call, então latência previsível vale mais que qualidade marginal.

### Falha isolada por URL

Uma URL que falha não derruba as outras. O corpo inteiro do laço, por URL, está protegido, incluindo a gravação e a leitura do cache. O vendedor prefere três resultados e um aviso a um erro geral.

### Degradação é explícita, nunca silenciosa

Quando o LLM falha e o sistema cai no extrator por regras, a resposta traz um campo próprio indicando a degradação, e a interface mostra uma tag de aviso com o motivo em uma linha. Sem detalhe técnico na tela do vendedor; o detalhe fica no log.

Se não avisasse, o vendedor concluiria que o produto é ruim em vez de entender que houve uma indisponibilidade.

### O par de padrões muda junto

O endpoint e o modelo são variáveis de ambiente e os padrões apontam para o mesmo provedor. Exportar só a chave já funciona de ponta a ponta.

A alternativa, deixar o endpoint apontando para um provedor e o modelo para outro, criaria uma armadilha: quem exportasse só a chave tomaria erro e degradaria em silêncio. Aqui a falha não ocorre, em vez de ser detectada.

### Coleta responsável

`robots.txt` é consultado antes de buscar, com timeout próprio e curto. O user-agent é identificável e traz contato. Existe limite de tamanho de página e validação de URL que rejeita endereços privados, loopback e reservados, revalidando a cada redirecionamento.

Essa última parte fecha o ataque mais óbvio contra um sistema que busca URLs enviadas pelo usuário: usar o servidor como ponte para alcançar a rede interna.

### Autorização vive no servidor

A interface esconde a área de administração de quem não é admin, e isso é conforto de uso, não controle de acesso. O HTML é o mesmo arquivo para todo mundo, então a seção existe no código-fonte da página.

O que controla é o servidor: cada rota declara sua guarda e o papel é lido da sessão gravada no banco, nunca de algo que o cliente envie. Forçar a seção a aparecer pelo inspetor do navegador não dá acesso a nada, as chamadas voltam 403.

Existe um teste que percorre todas as rotas registradas e compara com a lista declarada de guardas, exigindo igualdade entre os conjuntos. Rota nova sem guarda declarada quebra a suíte em vez de nascer aberta.

### Senhas e sessões

Senha guardada com scrypt, da biblioteca padrão do Python, com sal por usuário. A comparação usa tempo constante.

A sessão é um token opaco, guardado no banco apenas como resumo criptográfico, então vazar o banco não entrega sessões utilizáveis. Desativar um usuário encerra a sessão em curso, não só bloqueia logins futuros.

O primeiro administrador nasce de variáveis de ambiente na inicialização, sem cadastro público e sem senha embutida no código. A criação é idempotente: se o usuário já existe, nada é sobrescrito.

O login tem duas contagens de limite: por IP e por nome de usuário. E erro de login devolve sempre a mesma mensagem, seja usuário inexistente ou senha errada, para não entregar quais contas existem.

---

## O que ficou de fora, e por quê

| Fora do escopo | Motivo |
|---|---|
| Crawling de site inteiro | O usuário informa as páginas relevantes; crawler amplia custo e risco de bloqueio |
| Renderização de JavaScript | Site que só monta por JS devolve HTML vazio. Exigiria navegador headless |
| Busca de notícias em fontes externas | Amplia bastante o escopo; os sinais recentes vêm do próprio site |
| Conjunto de avaliação de prompt | Sem um conjunto de páginas com resultado esperado, "melhorei o prompt" é opinião. Próximo passo natural |

---

## Limites conhecidos

O banco é SQLite em arquivo único, adequado ao volume atual e não a dez vezes ele.

Não há métrica nem alerta: se quebrar, só se descobre pelo log.

O caminho de degradação da saída estruturada dispara apenas quando o provedor recusa o formato. Com o modelo em uso isso não acontece, então esse ramo é coberto só por teste com duplo, não contra o provedor real. "LLM verificado" não é "os dois caminhos verificados".

---

## Como usei IA

Montei o escopo do problema e discuti a solução antes de escrever qualquer linha. Definido o desenho, escrevi a especificação do projeto e passei para o Claude Code usando o fluxo GSD, que trabalha por fase: discutir, planejar, executar, verificar e entregar.

O que eu não deleguei: a definição do problema, as decisões de arquitetura e a aprovação de cada plano antes da execução. Cada decisão está registrada em `.planning/` com a alternativa que existia e o motivo da escolha.

A verificação encontrou coisas reais. O primeiro teste do extrator falhou porque a limpeza do HTML removia a tag de rodapé, que é justamente onde mora o contato da empresa. E a verificação da fase reproduziu duas rotas de exceção que escapavam da garantia de isolamento por URL, antes de corrigir.

Também vale registrar o limite: um dos verificadores automatizados reportou sucesso enquanto lia o arquivo errado, e o erro só apareceu porque alguém foi conferir. Automação de verificação também precisa ser verificada.

---

## Stack

Python 3.12, FastAPI, Pydantic, httpx, BeautifulSoup, SQLite, HTML servido pela própria API.

Sem framework de frontend: a interface é um arquivo único, servido pelo backend.
