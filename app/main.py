"""
API do Sales Intel.

Fluxo de uma requisicao:
  vendedor manda URLs
    -> tem cache valido? devolve
    -> senao: busca a pagina, extrai texto, gera briefing, salva, devolve
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .extractor import escolher_extrator
from .fetcher import FetchError, buscar_html, extrair_texto
from .schemas import Briefing, BriefingRequest, BriefingResponse

app = FastAPI(
    title="Sales Intel",
    description="Gera briefing de cliente a partir de links, para a equipe de vendas.",
    version="0.1.0",
)


@app.on_event("startup")
def inicializar() -> None:
    db.criar_tabelas()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/briefings", response_model=list[BriefingResponse])
def gerar_briefings(req: BriefingRequest) -> list[BriefingResponse]:
    """
    Recebe de 1 a 10 links e devolve um briefing por link.

    Um link que falha nao derruba os outros: cada URL e tratada de forma
    independente e o erro vira um briefing de confianca baixa explicando
    o que aconteceu. O vendedor prefere resultado parcial a erro 500.
    """
    extrator = escolher_extrator()
    resultados: list[BriefingResponse] = []

    for url_obj in req.urls:
        url = str(url_obj)

        if not req.forcar_atualizacao:
            cache = db.buscar(url)
            if cache is not None:
                dados, nome_extrator, coletado_em = cache
                resultados.append(
                    BriefingResponse(
                        url=url,
                        briefing=Briefing(**dados),
                        origem="cache",
                        extrator=nome_extrator,
                        coletado_em=coletado_em,
                    )
                )
                continue

        try:
            html = buscar_html(url)
            titulo, texto = extrair_texto(html)
            briefing = extrator.extrair(url, titulo, texto)
            coletado_em = db.salvar(url, briefing.model_dump(), extrator.nome)
            origem = "novo"
            nome_extrator = extrator.nome
        except FetchError as e:
            briefing = Briefing(
                empresa=url,
                resumo=f"Nao foi possivel coletar esta pagina. {e}",
                confianca="baixa",
            )
            coletado_em = datetime.now(timezone.utc)
            origem = "novo"
            nome_extrator = "falha"

        resultados.append(
            BriefingResponse(
                url=url,
                briefing=briefing,
                origem=origem,
                extrator=nome_extrator,
                coletado_em=coletado_em,
            )
        )

    return resultados


@app.get("/api/historico")
def historico(limite: int = 50) -> list[dict]:
    """Tela de admin: o que ja foi coletado."""
    return db.listar(limite)


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse("static/index.html")

