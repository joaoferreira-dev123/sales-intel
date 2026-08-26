# Phase 5: LLM - Mapa de Padrões

**Mapeado:** 2026-08-26
**Arquivos analisados:** 9 (7 modificados, 2 novos)
**Analogs encontrados:** 8 / 9

## File Classification

| Arquivo (novo/modificado) | Role | Data Flow | Analog mais próximo | Match Quality |
|---|---|---|---|---|
| `app/extractor.py` — `LLMExtractor.extrair()` | service | request-response | `HeuristicExtractor.extrair()` (mesmo arquivo, linhas 39-61) | exact (mesmo Protocol) |
| `app/extractor.py` — chamada HTTP ao provedor | service | request-response | `fetcher.py` `buscar_html()` (linhas 40-65) | role-match (uso de `httpx`) |
| `app/config.py` (NOVO) | config | request-response (leitura de env) | `os.getenv` inline em `extractor.py:77` | role-match (padrão a extrair p/ módulo dedicado) |
| `.env.example` (NOVO) | config | — | nenhum (arquivo não existe) | sem analog |
| `app/main.py` — segundo braço de `try/except` (falha de extrator) | controller/route | request-response | `except FetchError` em `main.py:75-83` | exact |
| `app/main.py` — `escolher_extrator()` por URL, dentro do laço | controller/route | request-response | mesmo arquivo, laço `for url_obj in req.urls` (linhas 50-93) | exact |
| `app/main.py` — `StaticFiles`/`FileResponse` com caminho absoluto | config | file-I/O | mesmo arquivo, linhas 104/109 (versão atual, a corrigir) | exact (correção local) |
| `app/schemas.py` — campo de degradação em `BriefingResponse` | model | CRUD (validação) | `BriefingResponse.extrator: str` (linhas 50-59) | exact (mesmo model, campo irmão) |
| `app/db.py` — regra de upgrade de extrator em `buscar()` | model/service | CRUD | `buscar()` atual (linhas 41-56) | exact (mesma função, extensão de regra) |
| `app/fetcher.py` — timeout em `parser.read()` | service | request-response | `buscar_html()` uso de `httpx.Client(timeout=TIMEOUT, ...)` (linha 46-47) | role-match (mesmo arquivo, padrão de timeout já estabelecido) |
| `static/index.html` — tag de degradação + fix mojibake | component | request-response (render client-side) | classe `.tag` existente (linha 27) e função `render()` (linhas 89-106) | exact |
| `test_smoke.py` — 4 testes novos (D-12) | test | request-response / CRUD | 3 testes existentes (linhas 15-31) | exact |

## Pattern Assignments

### `app/extractor.py` — `LLMExtractor.extrair()` (service, request-response)

**Analog primário:** `HeuristicExtractor.extrair()` (mesmo arquivo, linhas 39-61)
**Analog secundário para chamada HTTP:** `app/fetcher.py::buscar_html()` (linhas 40-65)

**Contrato a cumprir (Protocol, linhas 31-36):**
```python
class Extractor(Protocol):
    """Contrato que qualquer extrator precisa cumprir."""

    nome: str

    def extrair(self, url: str, titulo: str, texto: str) -> Briefing: ...
```

**Esqueleto atual a substituir** (linhas 83-89 — remover o `raise NotImplementedError`, manter `_trecho`):
```python
def extrair(self, url: str, titulo: str, texto: str) -> Briefing:
    if not self.disponivel():
        raise RuntimeError("Sem chave de API configurada.")
    # Corte de custo: texto longo demais nao melhora o resultado e
    # multiplica o preco por chamada.
    _trecho = texto[:12000]
    raise NotImplementedError("Chamada ao LLM entra quando a chave chegar.")
```
D-03/D-04: o corte de 12k passa a vir de `config.LLM_MAX_CHARS` em vez do literal `12000`. O `RuntimeError("Sem chave de API configurada.")` já é o padrão exigido pelo teste 4 de D-12 — reaproveitar literalmente essa mensagem/tipo.

**Padrão httpx a copiar de `fetcher.py:40-65`** (client como context manager, `timeout=`, tratamento de erro por tipo de exceção, mensagem curta e sem stack trace):
```python
try:
    with httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
except httpx.HTTPStatusError as e:
    raise FetchError(f"O site respondeu {e.response.status_code}.") from e
except httpx.RequestError as e:
    raise FetchError(f"Nao consegui alcancar o site: {type(e).__name__}") from e
```
Para o `LLMExtractor` (D-01, D-03): mesmo padrão de `httpx.Client(timeout=..., headers=...)`, mas `POST` ao endpoint de chat completions, `timeout=20.0` (não 15.0), sem retry. Erros de rede/HTTP devem virar uma exceção clara (ex.: `RuntimeError` ou uma nova exceção local) capturada em `main.py`, seguindo D-05/D-06 — nunca deixar propagar como 500.

**Honestidade de `confianca` (linha 60):**
```python
confianca="baixa",
```
No heurístico é sempre `"baixa"` por design. No `LLMExtractor`, `confianca` deve vir do próprio modelo (validado pelo schema `Briefing`), não hardcoded — mas ao degradar para heurístico por falha do LLM, a resposta resultante deve seguir o padrão de `confianca="baixa"` do heurístico (D-05: `extrator` continua `"heuristico"`).

**Saída estruturada (D-02):** gerar o schema JSON a partir de:
```python
Briefing.model_json_schema()
```
(chamada a fazer dentro de `app/extractor.py`, sem escrever schema manual) e validar a resposta do modelo com:
```python
Briefing(**dados)
```
mesma forma de instanciação já usada em `main.py:60` (`Briefing(**dados)` no caminho de cache) — reaproveitar esse padrão de validação na volta da chamada ao LLM.

---

### `app/config.py` (NOVO) (config, leitura de ambiente)

**Analog:** padrão atual inline em `extractor.py:77`:
```python
self.api_key = api_key or os.getenv("LLM_API_KEY")
```

Não há módulo `config.py` hoje — este é o primeiro. Seguir a convenção de constantes UPPER_SNAKE_CASE já usada em `fetcher.py` (`USER_AGENT`, `TIMEOUT`, `MAX_BYTES`) e `db.py` (`DB_PATH`, `VALIDADE`) como modelo de estilo para o módulo novo:
```python
# fetcher.py, linhas 17-20 — modelo de constantes de módulo
USER_AGENT = "bna-sales-intel/0.1 (+contato: gabriel@bna.dev.br)"
TIMEOUT = 15.0
MAX_BYTES = 3_000_000
```
D-04: `config.py` deve expor apenas `LLM_API_KEY`, `LLM_MODELO`, `LLM_MAX_CHARS`, lidos via `os.getenv` no carregamento do módulo (mesmo padrão de leitura simples já visto em `extractor.py:77`, apenas centralizado). Docstring de módulo no mesmo estilo dos demais arquivos (explicar o "porquê", ver `db.py:1-10` e `extractor.py:1-19`).

---

### `.env.example` (NOVO)

Sem analog no disco (arquivo não existe). Usar como referência as 3 variáveis de D-04 e o nome exato usado em `extractor.py:77` (`LLM_API_KEY`) e a proposta `LLM_MODELO`, `LLM_MAX_CHARS`. Sem código a copiar — apenas formato `CHAVE=valor` padrão dotenv.

---

### `app/main.py` — segundo braço de erro (falha do extrator) (controller, request-response)

**Analog:** bloco `except FetchError` já existente, **extraído verbatim** (linhas 75-83):
```python
except FetchError as e:
    briefing = Briefing(
        empresa=url,
        resumo=f"Nao foi possivel coletar esta pagina. {e}",
        confianca="baixa",
    )
    coletado_em = datetime.now(timezone.utc)
    origem = "novo"
    nome_extrator = "falha"
```
D-05/D-06: este é o padrão declarado para o novo braço que captura falha do `LLMExtractor.extrair()` — mesma estrutura (`Briefing` com `confianca="baixa"`, mensagem curta sem stack trace, `coletado_em = datetime.now(timezone.utc)`, `origem = "novo"`). Diferença chave: quando quem lançou é o extrator (não o `FetchError` do fetch), D-05 exige que `extrator` **permaneça `"heuristico"`** (não `"falha"`) e que o motivo da degradação vá para um **campo novo opcional em `BriefingResponse`**, não para `nome_extrator`. Isso significa reescrever o fluxo: tentar `LLMExtractor`, capturar a exceção, cair para `HeuristicExtractor().extrair(...)`, marcar `nome_extrator = "heuristico"` e preencher o novo campo de degradação com a mensagem curta (mesmo tom de `f"Nao foi possivel coletar esta pagina. {e}"`).

**Laço de seleção por URL (linhas 47, 50-93):** hoje `extrator = escolher_extrator()` está fora do laço (linha 47), violando L-02 (fallback por URL). O laço em si (linhas 50-93) é o analog estrutural a preservar — mover a chamada de `escolher_extrator()` para dentro do `for url_obj in req.urls:`.

---

### `app/main.py` — `StaticFiles` / `FileResponse` com caminho absoluto (config, file-I/O)

**Estado atual (a corrigir), linhas 104 e 109:**
```python
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def home() -> FileResponse:
    return FileResponse("static/index.html")
```
Sem analog externo — é uma correção local de caminho relativo para absoluto (ex.: via `pathlib.Path(__file__).resolve().parent.parent / "static"`), mantendo a mesma assinatura de rota e mesmo padrão de import (`from pathlib import Path`, já usado em `db.py:15`).

---

### `app/schemas.py` — campo de degradação em `BriefingResponse` (model, CRUD/validação)

**Analog:** o próprio `BriefingResponse` (linhas 50-59), campo `extrator` como modelo de como declarar um campo `Field` com descrição curta:
```python
class BriefingResponse(BaseModel):
    """O que a API devolve, com metadados de origem."""

    url: str
    briefing: Briefing
    origem: Literal["cache", "novo"] = Field(
        description="Se veio do banco (cache) ou foi raspado agora"
    )
    extrator: str = Field(description="Qual implementacao gerou: heuristico ou llm")
    coletado_em: datetime
```
D-05: adicionar campo opcional (ex.: `degradado: str | None = Field(default=None, description="Motivo da degradação, se houve")`), seguindo o mesmo estilo `Field(default=..., description=...)` já usado em `Briefing.segmento`/`porte_estimado` (`schemas.py:22-25`) para campos opcionais:
```python
segmento: str | None = Field(default=None, description="Setor de atuacao")
```

---

### `app/db.py` — regra de upgrade de extrator em `buscar()` (model/service, CRUD)

**Analog:** `buscar()` atual completo (linhas 41-56):
```python
def buscar(url: str) -> tuple[dict, str, datetime] | None:
    """Devolve (briefing, extrator, data) se houver cache valido."""
    with conectar() as conn:
        row = conn.execute(
            "SELECT briefing, extrator, coletado_em FROM briefings WHERE url = ?",
            (url,),
        ).fetchone()

    if row is None:
        return None

    coletado_em = datetime.fromisoformat(row["coletado_em"])
    if datetime.now(timezone.utc) - coletado_em > VALIDADE:
        return None  # existe, mas venceu

    return json.loads(row["briefing"]), row["extrator"], coletado_em
```
D-09: acrescentar parâmetro (ex.: `llm_disponivel: bool`) e, antes do `return` final, tratar como *miss* (`return None`) quando `row["extrator"] == "heuristico"` e `llm_disponivel` é `True`. Mesmo estilo de comentário inline explicando o "porquê" (`# existe, mas venceu` → adicionar comentário equivalente, ex. `# heuristico com LLM disponivel: forca recoleta`). Não altera schema da tabela (`CREATE TABLE`, linhas 27-38, permanece igual — D-10 explicitamente não mexe aqui).

---

### `app/fetcher.py` — timeout em `pode_raspar()` (service, request-response)

**Analog interno:** padrão de timeout já usado na chamada `httpx` da mesma função vizinha `buscar_html()`:
```python
TIMEOUT = 15.0
...
with httpx.Client(timeout=TIMEOUT, ...) as client:
```
**Trecho a corrigir (linhas 27-37):**
```python
def pode_raspar(url: str) -> bool:
    """Consulta o robots.txt do dominio. Se nao der para ler, assume que pode."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:
        return True
    return parser.can_fetch(USER_AGENT, url)
```
`RobotFileParser.read()` não aceita `timeout` diretamente — precisa reimplementar a leitura via `httpx.get(robots_url, timeout=TIMEOUT)` e alimentar `parser.parse()` com as linhas do corpo, mantendo o mesmo `try/except Exception: return True` (fail-open, já é o padrão declarado no docstring "se nao der para ler, assume que pode"). Reaproveitar a constante `TIMEOUT = 15.0` já definida no módulo (linha 19) em vez de criar um novo timeout.

---

### `static/index.html` — tag de degradação + correção de mojibake (component)

**Analog:** classe `.tag` (linha 27) e função `render()` (linhas 89-106):
```css
.tag { display:inline-block; background:#f4f6f9; border-radius:20px;
       padding:2px 10px; font-size:12px; margin-right:6px; }
```
```javascript
function render(r) {
  const b = r.briefing;
  return `<div class="card">
    <h2>${escapar(b.empresa)}</h2>
    <div class="meta">
      <span class="tag">${r.origem === 'cache' ? 'do cache' : 'coletado agora'}</span>
      <span class="tag">extrator: ${escapar(r.extrator)}</span>
      <span class="tag">confianÃ§a: ${escapar(b.confianca)}</span>
      ${escapar(r.url)}
    </div>
    <p>${escapar(b.resumo) || '<span class="vazio">sem resumo</span>'}</p>
    ...
```
D-07: adicionar uma quarta `<span class="tag">` condicional (renderizada apenas quando `r.degradado` existe), com uma variante de cor de atenção — reaproveitando a classe base `.tag` e adicionando um modificador CSS (ex. `.tag-aviso { background:#fde8e0; color:var(--accent); }`), seguindo o mesmo padrão de bloco `:root` de variáveis de cor já declarado no topo do `<style>` (linha 8, `--accent:#e4572e`).

**Correção de mojibake:** linhas 39 (`reuniÃ£o` → `reunião`), 96 (`confianÃ§a` → `confiança`), 102 (`dores provÃ¡veis` → `Dores prováveis`), e remover BOM do arquivo — reescrever o arquivo em UTF-8 sem BOM, sem alterar nenhuma outra estrutura HTML/JS.

---

### `test_smoke.py` — 4 testes novos (test, request-response/CRUD)

**Analog:** os 3 testes existentes (linhas 15-31), mesmo padrão de import direto de função pura e `assert` simples, sem fixtures nem mocks:
```python
"""Testes que rodam sem internet."""
from app.extractor import HeuristicExtractor
from app.fetcher import extrair_texto

HTML = """..."""

def test_extrair_texto_remove_script_e_pega_titulo():
    titulo, texto = extrair_texto(HTML)
    assert titulo == "Acme Tecnologia | Solucoes"
    assert "x=1" not in texto
    assert "automacao industrial" in texto

def test_heuristico_monta_briefing():
    titulo, texto = extrair_texto(HTML)
    b = HeuristicExtractor().extrair("https://acme.com.br", titulo, texto)
    assert b.empresa == "Acme Tecnologia"
    assert "automacao" in b.resumo
    assert b.confianca == "baixa"
```
D-12: os 4 testes novos seguem exatamente essa forma — função `test_*` solta no módulo, sem classe, sem fixture, `assert` direto. Para os testes 1 e 2 (`escolher_extrator()` com/sem chave), usar `monkeypatch.setenv("LLM_API_KEY", ...)` / `monkeypatch.delenv(...)` como parâmetro de função (`def test_x(monkeypatch):`), padrão pytest idiomático não visto ainda no arquivo mas compatível com o estilo funcional atual. Para o teste 3 (extrator lança exceção → resposta 200 com item degradado), usar `fastapi.testclient.TestClient` sobre `app.main.app` (import novo, ainda não usado no projeto — é o único ponto sem analog direto no repo, mas é o padrão FastAPI padrão para testar rotas). Para o teste 4 (`LLMExtractor.extrair()` sem chave levanta erro claro), replicar a forma do teste 2 do heurístico (chamar `.extrair(...)` diretamente e checar o resultado — aqui, com `pytest.raises(RuntimeError)` em vez de checar um campo do `Briefing`).

---

## Shared Patterns

### Falha vira resultado, nunca HTTP 500
**Fonte:** `app/main.py:75-83` (bloco `except FetchError`)
**Aplicar a:** `LLMExtractor.extrair()` (captura em `main.py`), regra de upgrade de cache (D-09), testes 3 e 4 de D-12.
```python
except FetchError as e:
    briefing = Briefing(
        empresa=url,
        resumo=f"Nao foi possivel coletar esta pagina. {e}",
        confianca="baixa",
    )
    coletado_em = datetime.now(timezone.utc)
    origem = "novo"
    nome_extrator = "falha"
```

### `httpx.Client` como context manager, com timeout explícito e tratamento por tipo de exceção
**Fonte:** `app/fetcher.py:46-56`
**Aplicar a:** chamada HTTP do `LLMExtractor` (D-01, D-03 — trocar `timeout=15.0` por `timeout=20.0`, sem retry).
```python
with httpx.Client(
    timeout=TIMEOUT,
    follow_redirects=True,
    headers={"User-Agent": USER_AGENT},
) as client:
    resp = client.get(url)
    resp.raise_for_status()
```

### `confianca` honesta — nunca inflar o campo
**Fonte:** `app/extractor.py:60` (`HeuristicExtractor`, sempre `"baixa"`)
**Aplicar a:** qualquer resposta de fallback/degradação (D-05), incluindo o novo braço de erro em `main.py`.

### Validação Pydantic na entrada e na saída
**Fonte:** `app/main.py:60` (`Briefing(**dados)` reconstruindo do cache)
**Aplicar a:** validação da saída do LLM em `LLMExtractor.extrair()` (D-02) — mesma forma `Briefing(**dados)`, deixando o `ValidationError` do Pydantic propagar como o "erro" exigido por L-03.

### Docstring de módulo explicando o "porquê" arquitetural
**Fonte:** `app/extractor.py:1-19`, `app/db.py:1-10`
**Aplicar a:** `app/config.py` (novo arquivo) — abrir com docstring de módulo no mesmo tom (curto, explica decisão, não implementação).

## No Analog Found

| Arquivo | Role | Data Flow | Motivo |
|---|---|---|---|
| `.env.example` | config | — | Arquivo não existe no disco; não há convenção de dotenv estabelecida no projeto ainda. Usar apenas as 3 variáveis de `config.py` (D-04) como conteúdo. |
| `fastapi.testclient.TestClient` (uso em `test_smoke.py`, teste 3 de D-12) | test | request-response | Nenhum teste atual sobe a aplicação FastAPI via `TestClient` — os 3 testes existentes testam funções puras, não rotas. Padrão a introduzir segue a documentação oficial do FastAPI (fora do repo). |

## Metadata

**Escopo da busca de analogs:** `app/*.py`, `static/index.html`, `test_smoke.py`, `requirements.txt`, `.planning/codebase/CONVENTIONS.md`
**Arquivos escaneados:** 8 arquivos de código + 1 doc de convenções
**Data da extração:** 2026-08-26
