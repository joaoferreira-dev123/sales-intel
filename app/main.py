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
from .extractor import HeuristicExtractor, escolher_extrator
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


def _extrair_com_fallback(url: str, titulo: str, texto: str) -> tuple[Briefing, str]:
    """
    Escolhe o extrator ativo para esta URL e degrada em tres degraus se
    ele falhar. Nenhuma rota desta funcao levanta excecao: falha de
    extrator vira resultado, nunca erro HTTP (SPEC SS6/SS10), porque o
    vendedor prefere briefing parcial a uma tela quebrada.
    """
    extrator = escolher_extrator()
    try:
        briefing = extrator.extrair(url, titulo, texto)
        return briefing, extrator.nome
    except Exception as erro_extrator:
        # Except amplo e proposital: qualquer falha do extrator principal
        # precisa degradar para o heuristico, e o tipo de erro do LLM
        # ainda nao existe nesta fase do plano.
        try:
            briefing = HeuristicExtractor().extrair(url, titulo, texto)
            return briefing, "heuristico"
        except Exception as erro_heuristico:
            briefing = Briefing(
                empresa=url,
                resumo=f"Nao foi possivel gerar o briefing. {erro_heuristico}",
                confianca="baixa",
            )
            return briefing, "falha"


@app.post("/api/briefings", response_model=list[BriefingResponse])
def gerar_briefings(req: BriefingRequest) -> list[BriefingResponse]:
    """
    Recebe de 1 a 10 links e devolve um briefing por link.

    Um link que falha nao derruba os outros: cada URL e tratada de forma
    independente e o erro vira um briefing de confianca baixa explicando
    o que aconteceu. O vendedor prefere resultado parcial a erro 500.
    """
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
            briefing, nome_extrator = _extrair_com_fallback(url, titulo, texto)
            if nome_extrator == "falha":
                coletado_em = datetime.now(timezone.utc)
            else:
                coletado_em = db.salvar(url, briefing.model_dump(), nome_extrator)
            origem = "novo"
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

