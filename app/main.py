"""
API do Sales Intel.

Fluxo de uma requisicao:
  vendedor manda URLs
    -> tem cache valido? devolve
    -> senao: busca a pagina, extrai texto, gera briefing, salva, devolve
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import auth, config, db
from .extractor import HeuristicExtractor, LLMError, escolher_extrator
from .fetcher import FetchError, buscar_html, extrair_texto
from .schemas import Briefing, BriefingRequest, BriefingResponse, LoginRequest, Usuario

app = FastAPI(
    title="Sales Intel",
    description="Gera briefing de cliente a partir de links, para a equipe de vendas.",
    version="0.1.0",
)

# Caminhos absolutos: servir a UI nao pode depender do working directory de
# onde o uvicorn foi iniciado.
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# L-02/D-05/D-06: literais autorados por nos. Nunca interpolamos str() de uma
# excecao nao autorada nestes campos — o vendedor le apenas a frase generica,
# nunca o texto arbitrario de uma falha de terceiro (SQLite, heuristico, etc).
AVISO_CACHE_INDISPONIVEL = "Briefing gerado, mas nao foi possivel gravar no cache."
MSG_FALHA_GENERICA = "Nao foi possivel gerar o briefing para este link."
MSG_NAO_AUTENTICADO = "Sessao ausente ou expirada. Faca login."
MSG_SEM_PERMISSAO = "Esta area e restrita a administradores."

# WR-04: sem nenhum controle, qualquer chamador anonimo drena custo de LLM
# ilimitado batendo em loop em /api/briefings (cada URL nao cacheada dispara
# uma chamada faturada quando LLM_API_KEY esta configurada). Um limite de
# taxa por IP, em memoria, fecha o abuso trivial de "loop de requisicoes"
# num prototipo de processo unico; nao substitui um API-gateway/API-key em
# producao atras de multiplos workers, mas e a barreira minima descrita no
# achado. Estado global de proposito: precisa sobreviver entre requisicoes
# do mesmo processo.
_RATE_LIMIT_JANELA = timedelta(minutes=1)
_RATE_LIMIT_MAX_REQUISICOES = 20  # por IP, por janela
_rate_limit_lock = Lock()
_requisicoes_por_ip: dict[str, list[datetime]] = {}


def _checar_rate_limit(request: Request) -> None:
    """Dependency do FastAPI: levanta 429 se o IP do chamador excedeu o
    limite de requisicoes na janela atual. Chamada antes de qualquer fetch
    ou chamada de LLM."""
    ip = request.client.host if request.client else "desconhecido"
    agora = datetime.now(timezone.utc)
    limite_inferior = agora - _RATE_LIMIT_JANELA
    with _rate_limit_lock:
        historico = _requisicoes_por_ip.setdefault(ip, [])
        historico[:] = [t for t in historico if t >= limite_inferior]
        if len(historico) >= _RATE_LIMIT_MAX_REQUISICOES:
            raise HTTPException(
                status_code=429,
                detail="Muitas requisicoes deste endereco. Tente novamente em instantes.",
            )
        historico.append(agora)


# Limite de forca bruta no login (T-06-13/T-06-14). Estado proprio, separado
# de `_requisicoes_por_ip` acima, para nao competir com o limitador da rota
# de briefings.
#
# (a) Duas contagens, nao uma: so por IP deixa passar pulverizacao
#     distribuida contra uma unica conta (varias origens tentando o mesmo
#     username); so por username deixa um atacante trancar a conta de um
#     vendedor legitimo so martelando login com senha errada.
# (b) Janela deslizante, nao bloqueio: nao existe estado de "conta
#     bloqueada" que um terceiro possa induzir contra outra pessoa — um
#     sucesso limpa o contador do username, e a janela expira sozinha.
# (c) Estado em memoria de um processo unico, com a mesma limitacao ja
#     declarada em WR-04 — nao sobrevive a reinicio nem a multiplos workers.
_LOGIN_JANELA = timedelta(minutes=5)
_LOGIN_MAX_POR_IP = 10  # toda tentativa daquele endereco conta
_LOGIN_MAX_FALHAS_POR_USUARIO = 5  # so falha conta; sucesso limpa a lista
_login_lock = Lock()
_tentativas_login_por_ip: dict[str, list[datetime]] = {}
_falhas_login_por_usuario: dict[str, list[datetime]] = {}

# Mensagem de 429 e literal autorado e nao revela se o username existe.
MSG_LOGIN_MUITAS_TENTATIVAS = "Muitas tentativas de login. Tente novamente em instantes."


def _checar_limite_login_por_ip(request: Request) -> None:
    """Dependency do FastAPI: levanta 429 se o IP do chamador excedeu o
    limite de tentativas de login na janela atual."""
    ip = request.client.host if request.client else "desconhecido"
    agora = datetime.now(timezone.utc)
    limite_inferior = agora - _LOGIN_JANELA
    with _login_lock:
        historico = _tentativas_login_por_ip.setdefault(ip, [])
        historico[:] = [t for t in historico if t >= limite_inferior]
        if len(historico) >= _LOGIN_MAX_POR_IP:
            raise HTTPException(status_code=429, detail=MSG_LOGIN_MUITAS_TENTATIVAS)
        historico.append(agora)


def _checar_limite_login_por_usuario(username: str) -> None:
    """Levanta 429 se o username excedeu o limite de falhas na janela
    atual. Chamada dentro do corpo da rota de login, antes de
    `auth.autenticar`, porque o username so existe depois do corpo da
    requisicao ser desserializado."""
    agora = datetime.now(timezone.utc)
    limite_inferior = agora - _LOGIN_JANELA
    with _login_lock:
        falhas = _falhas_login_por_usuario.setdefault(username, [])
        falhas[:] = [t for t in falhas if t >= limite_inferior]
        if len(falhas) >= _LOGIN_MAX_FALHAS_POR_USUARIO:
            raise HTTPException(status_code=429, detail=MSG_LOGIN_MUITAS_TENTATIVAS)


def _registrar_falha_de_login(username: str) -> None:
    """Registra uma falha de autenticacao para o username. Chamada quando
    `auth.autenticar` devolve None."""
    agora = datetime.now(timezone.utc)
    with _login_lock:
        _falhas_login_por_usuario.setdefault(username, []).append(agora)


def _limpar_falhas_de_login(username: str) -> None:
    """Zera o contador de falhas do username. Chamada no caminho de
    sucesso: um login valido nao deixa uma conta em estado bloqueado."""
    with _login_lock:
        _falhas_login_por_usuario.pop(username, None)


def usuario_atual(request: Request) -> Usuario:
    """Dependency do FastAPI: le o cookie de sessao e devolve o usuario
    autenticado. Sem cookie ou com sessao invalida levanta 401. Ligada as
    rotas por `Depends(usuario_atual)` como parametro (nao em
    `dependencies=[...]`, que descartaria o retorno) porque `exigir_admin`
    e as proprias rotas precisam do usuario resolvido (D-17)."""
    token = request.cookies.get(auth.NOME_COOKIE_SESSAO)
    usuario = auth.validar_sessao(token) if token else None
    if usuario is None:
        raise HTTPException(status_code=401, detail=MSG_NAO_AUTENTICADO)
    return Usuario(**usuario)


def exigir_admin(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
    """Dependency composta sobre `usuario_atual`: levanta 403 quando o
    papel do usuario autenticado nao e admin. E esta composicao que produz
    401 (sem sessao) e 403 (sessao sem privilegio) como dois estados
    distintos, ambos avaliados no servidor a cada requisicao (L-07, D-17)."""
    if usuario.papel != "admin":
        raise HTTPException(status_code=403, detail=MSG_SEM_PERMISSAO)
    return usuario


@app.on_event("startup")
def inicializar() -> None:
    db.criar_tabelas()
    # D-19: seed do primeiro admin depois da tabela existir. Sem as duas
    # variaveis de ambiente, devolve None e o processo sobe normalmente.
    auth.semear_admin_inicial()


@app.get("/health")
def health() -> dict:
    # D-08: extensao aditiva ao contrato da SPEC SS10 — "status" continua
    # "ok", e o campo novo so informa o modo de operacao, sem expor a chave.
    return {"status": "ok", "llm_disponivel": bool(config.llm_api_key())}


@app.post(
    "/api/auth/login",
    response_model=Usuario,
    dependencies=[Depends(_checar_limite_login_por_ip)],
)
def login(dados: LoginRequest, request: Request, resposta: Response) -> Usuario:
    """Autentica por username e senha. Nenhum caminho emite sessao antes da
    autenticacao — e o que fecha fixacao de sessao (T-06-07)."""
    _checar_limite_login_por_usuario(dados.username)

    usuario = auth.autenticar(dados.username, dados.senha)
    if usuario is None:
        _registrar_falha_de_login(dados.username)
        raise HTTPException(status_code=401, detail=auth.MSG_LOGIN_INVALIDO)

    # Login bem-sucedido zera o contador de falhas do username: nao existe
    # conta em estado bloqueado (T-06-14).
    _limpar_falhas_de_login(dados.username)

    # Login bem-sucedido sempre emite token novo e sobrescreve o cookie.
    token = auth.criar_sessao(usuario["id"])
    resposta.set_cookie(
        key=auth.NOME_COOKIE_SESSAO,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=int(auth.DURACAO_SESSAO.total_seconds()),
        # D-16: a demo roda em http local; um cookie secure em http
        # simplesmente nao seria enviado. Liga sozinho quando o esquema da
        # requisicao e https.
        secure=request.url.scheme == "https",
    )
    return Usuario(**usuario)


@app.get("/api/auth/me", response_model=Usuario)
def eu(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
    """A UI usa esta rota para decidir o que desenhar (papel do usuario logado)."""
    return usuario


@app.get("/api/admin/usuarios", response_model=list[Usuario])
def listar_usuarios(usuario: Usuario = Depends(exigir_admin)) -> list[Usuario]:
    """Lista de usuarios, restrita a admin (L-07/T-06-10)."""
    return [Usuario(**u) for u in auth.listar_usuarios()]


@app.post("/api/auth/logout")
def logout(
    request: Request, resposta: Response, usuario: Usuario = Depends(usuario_atual)
) -> dict:
    """Encerra a sessao no servidor. Exigir `usuario_atual` e deliberado:
    sem sessao valida nao ha o que encerrar, e mantem a regra de que toda
    rota de /api/ tem guarda declarada."""
    token = request.cookies.get(auth.NOME_COOKIE_SESSAO)
    if token:
        auth.encerrar_sessao(token)
    resposta.delete_cookie(key=auth.NOME_COOKIE_SESSAO, path="/")
    return {"status": "ok"}


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
            # generica nesse caso. Mesma regra vale no degrau abaixo (excecao
            # do heuristico) e na guarda de gravacao no cache em
            # gerar_briefings: so interpolamos mensagem autorada por nos.
            degradado = "IA indisponivel, briefing gerado por regras."
            if isinstance(erro_extrator, LLMError):
                degradado = f"{degradado} {erro_extrator}"
            degradado = degradado[:200]
            return briefing, "heuristico", degradado
        except Exception:
            # D-06: mesma regra do degrau acima — so interpolamos str() de
            # excecao autorada por nos. O heuristico pode, numa mudanca
            # futura, levantar qualquer coisa; sem nome, nao ha nada seguro
            # a fazer com ela num campo que o vendedor le.
            briefing = Briefing(
                empresa=url,
                resumo=MSG_FALHA_GENERICA,
                confianca="baixa",
            )
            return briefing, "falha", None


@app.post(
    "/api/briefings",
    response_model=list[BriefingResponse],
    dependencies=[Depends(_checar_rate_limit)],
)
def gerar_briefings(
    req: BriefingRequest, usuario: Usuario = Depends(usuario_atual)
) -> list[BriefingResponse]:
    """
    Recebe de 1 a 10 links e devolve um briefing por link.

    Um link que falha nao derruba os outros: cada URL e tratada de forma
    independente e o erro vira um briefing de confianca baixa explicando
    o que aconteceu. O vendedor prefere resultado parcial a erro 500.

    D-17/T-06-27: exige sessao (`usuario_atual`), alem do limite por IP
    (`_checar_rate_limit`) — sao dois controles diferentes, e nenhum
    substitui o outro. D-18: cada briefing gravado registra o dono a
    partir da sessao, nunca de um campo do corpo da requisicao.
    """
    resultados: list[BriefingResponse] = []

    for url_obj in req.urls:
        url = str(url_obj)

        # L-02: o try sobe para cobrir o corpo por URL inteiro (cache, fetch,
        # extracao, gravacao). Nao e so as duas rotas que a verificacao
        # reproduziu: e a garantia de que nenhuma excecao desta URL derruba as
        # demais do mesmo lote.
        try:
            if not req.forcar_atualizacao:
                # Mesma fonte consultada por escolher_extrator() e por /health, para
                # que os tres nunca discordem sobre o modo de operacao (D-09).
                cache = db.buscar(url, llm_disponivel=bool(config.llm_api_key()))
                if cache is not None:
                    # L-02/D-10: uma linha gravada por uma versao anterior do
                    # schema e dado velho, nao erro do usuario — o tratamento
                    # correto e recoletar, nunca corrigir ou apagar a linha.
                    # Captura estreita (nao Exception largo): mantem a
                    # distincao entre "linha velha, recolete" e "erro
                    # inesperado, degrade a URL" (o catch-all abaixo continua
                    # sendo a rede embaixo).
                    resposta_cache = None
                    try:
                        dados, nome_extrator, coletado_em = cache
                        resposta_cache = BriefingResponse(
                            url=url,
                            briefing=Briefing(**dados),
                            origem="cache",
                            extrator=nome_extrator,
                            coletado_em=coletado_em,
                        )
                    except (ValidationError, TypeError):
                        pass
                    if resposta_cache is not None:
                        resultados.append(resposta_cache)
                        continue

            html = buscar_html(url)
            titulo, texto = extrair_texto(html)
            briefing, nome_extrator, degradado = _extrair_com_fallback(url, titulo, texto)
            if nome_extrator == "falha":
                coletado_em = datetime.now(timezone.utc)
            else:
                try:
                    coletado_em = db.salvar(
                        url, briefing.model_dump(), nome_extrator, dono=usuario.id
                    )
                except Exception:
                    # L-02: falha de gravacao no cache e falha de otimizacao, nao
                    # motivo para descartar um briefing ja gerado com sucesso.
                    # Nao interpolamos str() da excecao: uma falha de SQLite nao
                    # e mensagem autorada por nos (D-06) — o vendedor le apenas
                    # o aviso generico.
                    coletado_em = datetime.now(timezone.utc)
                    if degradado is None:
                        degradado = AVISO_CACHE_INDISPONIVEL
                    else:
                        degradado = f"{degradado} {AVISO_CACHE_INDISPONIVEL}"[:200]
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
        except Exception:
            # L-02: garantia estrutural. Cobre a CLASSE de falhas fora do fetch
            # e do extrator (gravacao, leitura de cache, desserializacao), nao
            # so as duas rotas nomeadas pela verificacao — uma quarta rota nao
            # deve poder reabrir este gap. Sem nome: nao ha nada seguro a fazer
            # com a excecao num campo que o vendedor le (D-06).
            briefing = Briefing(
                empresa=url,
                resumo=MSG_FALHA_GENERICA,
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
def historico(limite: int = 50, usuario: Usuario = Depends(usuario_atual)) -> list[dict]:
    """O que ja foi coletado. D-18: o recorte de visibilidade vem da
    sessao, nunca de um parametro de consulta — admin ve tudo, qualquer
    outro papel ve so o que ele proprio gerou. Um dono forjado na URL
    nao alcancaria nada, porque a rota nao aceita esse parametro (IDOR)."""
    if usuario.papel == "admin":
        return db.listar(limite, ver_tudo=True)
    return db.listar(limite, dono=usuario.id)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")

