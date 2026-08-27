# UAI Repasse

Sistema interno de anúncios de veículos para o grupo de repasse da **UAI Veículos**.

Substitui o fluxo manual de digitar specs e enviar fotos uma a uma no WhatsApp por:

1. **Admin web app** (interno, protegido por senha) — cadastra o carro uma vez, sobe as fotos em resolução cheia e gera o anúncio.
2. **Página pública por carro** (`/c/{slug}`) — URL compartilhável, somente leitura, com todas as fotos em qualidade total + a ficha completa.
3. **Fluxo de compartilhamento** — copia a legenda (texto do anúncio + link) e cola no grupo. O link gera um card de preview correto no WhatsApp (Open Graph).

A página pública é o ponto central: o comprador clica no link e vê as fotos sozinho, em vez de receber fotos pingadas no chat.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend / API | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Banco | PostgreSQL |
| Página pública | Server-rendered HTML (FastAPI + Jinja2) — emite Open Graph para o preview do WhatsApp |
| Admin | React + Vite (mobile-first) |
| Imagens | Disco local sob `MEDIA_ROOT`, atrás da abstração `MediaStorage` (trocável por S3/R2) |
| Auth | Contas por usuário com papéis (Vendedor/Gerente/Proprietário), senha argon2id, papel resolvido do banco a cada request → JWT (Bearer) |

---

## Estrutura

```
backend/
  app/
    main.py            # FastAPI app
    config.py          # settings via .env
    database.py        # engine + session
    models.py          # cars, photos, settings
    schemas.py         # Pydantic v2
    auth.py            # contas por usuário (argon2id) -> JWT
    listing.py         # build_listing() — gerador da legenda
    slugs.py           # slug único com sufixo numérico
    storage.py         # MediaStorage (LocalMediaStorage v1)
    images.py          # thumbnail + blur opcional
    serialization.py   # ORM -> schemas com URLs de mídia
    routers/{auth,admin,public}.py
    templates/{car,index}.html   # páginas públicas (OG tags)
    static/logo.png
  alembic/             # migrations (0001_initial + seed de settings)
  tests/test_listing.py
  Dockerfile, entrypoint.sh, requirements.txt
frontend/              # React + Vite admin (login, lista, form, detalhe, settings)
docker-compose.yml     # Postgres + app
.env.example
```

---

## Configuração (`.env`)

Copie `.env.example` para `.env` e ajuste:

```
# Host port 5433 (não 5432) para não colidir com o Postgres da concessionária.
DATABASE_URL=postgresql+psycopg://uai:uai@localhost:5433/uai_repasse

# O app NÃO inicia se JWT_SECRET for placeholder ou < 16 chars.
# Gere o JWT com: python -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_SECRET=replace-with-generated-48-char-secret

# Semeia a primeira conta (Proprietário) no primeiro boot; depois pode remover.
BOOTSTRAP_OWNER_USER=dono
BOOTSTRAP_OWNER_PASSWORD=set-a-strong-owner-password

PUBLIC_BASE_URL=https://repasse.uaiveiculos.com   # URLs absolutas (OG + links)
SELLER_WHATSAPP=5519993955686                     # E.164 sem +, para wa.me
BLUR_PLATES=false                                 # LGPD opcional: borra placas/rostos
MEDIA_ROOT=./media
JWT_EXPIRE_MINUTES=480                             # ~8h
ADMIN_ORIGIN=http://localhost:5173                 # origem permitida no CORS
DEBUG=false                                        # true habilita /docs (só dev)

# Produção (docker-compose.prod.yml + Caddy):
POSTGRES_PASSWORD=set-a-strong-db-password         # NÃO use "uai" em produção
PUBLIC_DOMAIN=repasse.uaiveiculos.com
ADMIN_DOMAIN=admin.uaiveiculos.com
ACME_EMAIL=you@uaiveiculos.com
```

> **`PUBLIC_BASE_URL` é crítico:** as tags `og:image` precisam de URL **absoluta**. Em produção aponte para o domínio público real (https), senão o preview do WhatsApp não renderiza a imagem.

---

## Dev local

> **Backend roda em Docker (Python 3.12 estável).** O Python local mais recente
> (3.14) ainda não tem wheels para `psycopg`, `Pillow` e `pydantic-core`, então
> rodar o backend no container é o caminho confiável. As migrations rodam
> automaticamente no `entrypoint.sh` ao subir o container.

### 1. Banco + API (Docker)

```bash
cp .env.example .env        # edite JWT_SECRET, BOOTSTRAP_OWNER_USER/PASSWORD, etc.
docker compose up -d --build
```

Isso sobe:
- **db** — Postgres no host **5433** (interno `db:5432`), volume `pgdata`.
- **app** — roda `alembic upgrade head` (cria tabelas + seed de settings) e o
  Uvicorn na porta **8000**.

API em `http://localhost:8000` · docs em `/docs` · página pública em `/c/{slug}` · índice em `/`.

Ver logs / rodar migrations manualmente no container:

```bash
docker compose logs -f app
docker compose exec app alembic upgrade head
```

### 2. Frontend (admin)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxy /api, /media, /c -> :8000)
```

Login com sua conta de usuário (usuário + senha). A primeira conta (Proprietário) é semeada no primeiro boot a partir de `BOOTSTRAP_OWNER_USER` / `BOOTSTRAP_OWNER_PASSWORD` no `.env`; as demais são criadas pelo Proprietário no admin.

### Testes

`build_listing()` é puro (sem banco) e roda local sem Docker, ou no container:

```bash
docker compose exec app pytest         # dentro do container
# ou, com Python 3.11/3.12 local: cd backend && pip install -r requirements.txt && pytest
```

### (Opcional) Backend local sem Docker

Funciona apenas com **Python 3.11 ou 3.12** (os pins têm wheels para essas
versões). Em 3.14 a instalação falha — use Docker.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    |  Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000   # precisa do db do compose no 5433
```

---

## Produção com Docker Compose + Caddy (HTTPS)

A produção usa um arquivo separado — `docker-compose.prod.yml` — para não mexer
no fluxo de dev. Ele sobe **db + app + Caddy**, com Caddy terminando HTTPS
(Let's Encrypt automático) como **único serviço exposto em 80/443**. O Postgres
**não** publica porta no host e usa senha forte de env var.

```bash
# 1. Preencha o .env com valores de produção:
#    POSTGRES_PASSWORD (forte, != "uai"), JWT_SECRET, BOOTSTRAP_OWNER_USER/PASSWORD,
#    PUBLIC_BASE_URL=https://<PUBLIC_DOMAIN>, ADMIN_ORIGIN=https://<ADMIN_DOMAIN>,
#    PUBLIC_DOMAIN, ADMIN_DOMAIN, ACME_EMAIL
cp .env.example .env && nano .env

# 2. Gere o admin estático (servido pelo Caddy):
cd frontend && npm ci && npm run build && cd ..

# 3. Suba a stack de produção:
docker compose -f docker-compose.prod.yml up -d --build
```

- DNS: aponte `PUBLIC_DOMAIN` e `ADMIN_DOMAIN` (A/AAAA) para o IP do servidor
  **antes** de subir — o Caddy precisa resolver os domínios para emitir os certs.
- O serviço `app` roda `alembic upgrade head` no start (`entrypoint.sh`).
- Fotos persistem no volume `media`; Postgres em `pgdata`; certs em `caddy_data`.
- Caddy serve o admin (`frontend/dist`) em `ADMIN_DOMAIN` e faz proxy de
  `/api`, `/media`, `/static` para o app (mesma origem → sem CORS). O site
  público fica em `PUBLIC_DOMAIN`.
- Suba o `logo.png` real em `backend/app/static/logo.png` (público) e
  `frontend/public/logo.png` (admin, antes do `npm run build`).

---

## Segurança (hardening proporcional)

Aplicado para um tool interno de operador único com superfície pública só-leitura:

- **Boot seguro** — o app recusa iniciar se `JWT_SECRET` for placeholder ou
  < 16 chars (falha com mensagem clara).
- **Login** — contas por usuário (senha argon2id); rate-limit ~5 tentativas/min
  por IP + bloqueio curto; mensagem genérica (`Credenciais inválidas`); JWT
  por usuário expira em ~8h.
- **Exposição** — `/docs`, `/redoc` e `/openapi.json` desligados fora de
  `DEBUG`; CORS travado em `ADMIN_ORIGIN` (sem `*`); porta do Postgres não
  publicada em produção.
- **Uploads** — todo arquivo é validado abrindo com Pillow (ignora extensão/
  content-type), limite de 12 MB/arquivo, re-encode que **remove EXIF**
  (GPS/localização de fotos de celular) e nome de arquivo aleatório (UUID).
- **Erros & headers** — sem stack trace ao cliente em produção (500 genérico,
  detalhe só no log); headers `X-Content-Type-Options`, `Referrer-Policy`,
  `X-Frame-Options`/`frame-ancestors` (anti-iframe) e HSTS sob HTTPS.
- **HTTPS** — Caddy com Let's Encrypt automático (ver seção de produção).

---

## Rodízio de vendedores (botão WhatsApp público)

O botão **"Tenho interesse"** de cada página pública não aponta para um número
fixo: ele aponta para `GET /c/{slug}/contato`. Esse endpoint, a cada clique,
entrega o próximo vendedor da lista em **rodízio global e server-side** e
redireciona (302) para o `wa.me` dele com a mensagem
`Olá! Tenho interesse no {modelo} {ano} — {link}`.

- O cursor (`rotation_index`) vive na tabela `settings` e é incrementado de forma
  **atômica** (`UPDATE ... RETURNING`), então dois cliques simultâneos pegam
  vendedores diferentes. É compartilhado entre todos os visitantes e todos os
  carros — nada é guardado no navegador.
- Após o último vendedor, volta ao primeiro. Adicionar/remover vendedores só
  muda o tamanho do ciclo (o índice é aplicado com módulo sobre a lista atual).
- **Lista vazia:** cai no número padrão `SELLER_WHATSAPP`; se também não houver,
  o clique apenas volta para a página do carro (nunca quebra).

**Gerenciar no admin:** _Configurações → Vendedores (rodízio do botão WhatsApp)_.
- **Adicionar:** botão "+ Adicionar vendedor", preencha nome e WhatsApp (E.164 só
  dígitos, ex. `5519993955686`).
- **Editar:** altere os campos na linha.
- **Remover:** botão `×` na linha.
- **Reordenar:** setas `↑` / `↓` — a ordem é a ordem do rodízio.
- Clique em **Salvar**. Linhas totalmente vazias são descartadas; o backend
  remove qualquer caractere não numérico do WhatsApp automaticamente.

> Já tem um banco rodando? Aplique a migration nova: `docker compose exec app
> alembic upgrade head` (ou `alembic upgrade head` local). Ela adiciona as colunas
> e semeia Silvinho, Lucas Oliveira e Marcos Faustino, nessa ordem.

---

## Verificando as tags Open Graph (preview do WhatsApp)

Depois de publicar um carro com fotos:

1. Abra `https://seu-dominio/c/{slug}` e confira no HTML as metatags `og:title`, `og:description`, `og:image` (URL **absoluta**), `og:type`, `twitter:card`.
2. Teste o card sem spammar o grupo:
   - Cole o link em uma conversa privada de teste no WhatsApp, **ou**
   - Use um validador de link preview (ex.: opengraph.xyz, ou o Sharing Debugger do Facebook) apontando para a URL pública.
3. A primeira foto (`position = 0`) é a imagem do card. Reordene no admin se quiser outra.

> O WhatsApp faz cache agressivo do preview por URL. Se atualizar a foto principal, o card antigo pode persistir por um tempo — adicione um query string novo ou aguarde o cache expirar.

---

## Modelo de dados (resumo)

- **cars** — `slug` (único, derivado de modelo+ano), specs, `acabamento`/`destaques` (JSONB arrays), `fipe`, `preco`, `sinistro`, `leilao`, `status` (`disponivel` | `oculto` | `vendido`). Só `disponivel` é público; os demais retornam 404 na página pública mas continuam editáveis no admin.
- **photos** — `path` (full-res), `thumb_path`, `position` (a primeira é a imagem OG). `ON DELETE CASCADE`.
- **settings** — linha única (`id=1`): `grupo`, `vendedor`, `telefone`, `rodape`. Semeada na migration inicial com os defaults da UAI.

## Gerador da legenda

`app/listing.py::build_listing(car, settings, public_url) -> str` reproduz exatamente o formato/emoji do anúncio, omitindo linhas de campos vazios. Números em pt-BR (milhar `.`, decimal `,`). Coberto por testes em `tests/test_listing.py`.

---

## Não-objetivos (fora do escopo)

Sem lances/leilão ao vivo na página · sem pagamento (o botão é só um deep link wa.me) · sem API oficial do WhatsApp (compartilhamento é copiar/colar) · sem geração de PDF.
