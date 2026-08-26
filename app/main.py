"""
API do Sales Intel.

Fluxo de uma requisicao:
  vendedor manda URLs
    -> tem cache valido? devolve
    -> senao: busca a pagina, extrai texto, gera briefing, salva, devolve
"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, db
from .extractor import HeuristicExtractor, LLMError, escolher_extrator
from .fetcher import FetchError, buscar_html, extrair_texto
from .schemas import Briefing, BriefingRequest, BriefingResponse

app = FastAPI(
    title="Sales Intel",
    description="Gera briefing de cliente a partir de links, para a equipe de vendas.",
    version="0.1.0",
)

# Caminhos absolutos: servir a UI nao pode depender do working directory de
# onde o uvicorn foi iniciado.
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


@app.on_event("startup")
def inicializar() -> None:
    db.criar_tabelas()


@app.get("/health")
def health() -> dict:
    # D-08: extensao aditiva ao contrato da SPEC SS10 — "status" continua
    # "ok", e o campo novo so informa o modo de operacao, sem expor a chave.
    return {"status": "ok", "llm_disponivel": bool(config.llm_api_key())}


def _extrair_com_fallback(
    url: str, titulo: str, texto: str
) -> tuple[Briefing, str, str | None]:
    """
    Escolhe o extrator ativo para esta URL e degrada em tres degraus se
    ele falhar. Nenhuma rota desta funcao levanta excecao: falha de
    extrator vira resultado, nunca erro HTTP (SPEC SS6/SS10), porque o
    vendedor prefere briefing parcial a uma tela quebrada.

    O terceiro elemento devolvido e o motivo da degradacao (D-05), separado
    de `extrator` para nao poluir a enumeracao da SPEC SS8.
    """
    extrator = escolher_extrator()
    try:
        briefing = extrator.extrair(url, titulo, texto)
        return briefing, extrator.nome, None
    except Exception as erro_extrator:
        # Except amplo e proposital: qualquer falha do extrator principal
        # precisa degradar para o heuristico, e o tipo de erro do LLM
        # ainda nao existe nesta fase do plano.
        try:
            briefing = HeuristicExtractor().extrair(url, titulo, texto)
            # D-06: so interpola str(erro_extrator) quando a excecao e
            # LLMError, porque essas mensagens sao escritas e auditadas por
            # nos (plano 05). Qualquer outra excecao pode carregar texto
            # arbitrario de terceiro, entao o vendedor le apenas a frase
            # generica nesse caso.
            degradado = "IA indisponivel, briefing gerado por regras."
            if isinstance(erro_extrator, LLMError):
                degradado = f"{degradado} {erro_extrator}"
            degradado = degradado[:200]
            return briefing, "heuristico", degradado
        except Exception as erro_heuristico:
            briefing = Briefing(
                empresa=url,
                resumo=f"Nao foi possivel gerar o briefing. {erro_heuristico}",
                confianca="baixa",
            )
            return briefing, "falha", None


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
            # Mesma fonte consultada por escolher_extrator() e por /health, para
            # que os tres nunca discordem sobre o modo de operacao (D-09).
            cache = db.buscar(url, llm_disponivel=bool(config.llm_api_key()))
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
            briefing, nome_extrator, degradado = _extrair_com_fallback(url, titulo, texto)
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
            degradado = None

        resultados.append(
            BriefingResponse(
                url=url,
                briefing=briefing,
                origem=origem,
                extrator=nome_extrator,
                degradado=degradado,
                coletado_em=coletado_em,
            )
        )

    return resultados


@app.get("/api/historico")
def historico(limite: int = 50) -> list[dict]:
    """Tela de admin: o que ja foi coletado."""
    return db.listar(limite)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")

