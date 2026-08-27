"""
Busca a pagina e extrai o texto legivel.

Duas responsabilidades separadas de proposito:
  - buscar (rede, pode falhar, precisa de timeout)
  - extrair texto (puro, testavel sem internet)
"""

import ipaddress
import socket
import urllib.robotparser
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

# User-agent identificavel. Raspar escondido e o tipo de coisa que da
# problema legal quando o sistema roda no servidor do cliente.
USER_AGENT = "bna-sales-intel/0.1 (+contato: gabriel@bna.dev.br)"

TIMEOUT = 15.0
MAX_BYTES = 3_000_000  # 3 MB: pagina maior que isso quase sempre e lixo
# Robots.txt e um arquivo minusculo e bloqueia o trabalho de verdade; esperar
# 15s (TIMEOUT) por ele significaria ate 30s por URL no pior caso.
ROBOTS_TIMEOUT = 5.0
# CR-01: teto de redirecionamentos manuais. Cada hop e revalidado contra
# endereco privado antes de ser seguido (ver _validar_url_publica).
MAX_REDIRECTS = 5


class FetchError(Exception):
    """Falha ao buscar a pagina. Guarda o motivo para mostrar ao vendedor."""


def _host_e_publico(host: str) -> bool:
    """CR-01: resolve o host e recusa qualquer endereco privado, loopback,
    link-local (inclui o endereco de metadados de nuvem 169.254.169.254),
    multicast ou reservado. Sem isso, qualquer chamador anonimo consegue
    usar este servico como proxy SSRF contra a rede onde ele roda."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for *_resto, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def _validar_url_publica(url: str) -> None:
    """CR-01: levanta FetchError se o host da URL nao resolver para um
    endereco publico. Chamada antes de qualquer conexao de saida (busca
    principal, robots.txt e cada hop de redirecionamento)."""
    host = urlparse(url).hostname
    if not host or not _host_e_publico(host):
        raise FetchError("Este endereco nao pode ser coletado.")


def pode_raspar(url: str) -> bool:
    """Consulta o robots.txt do dominio. Se nao der para ler, assume que pode."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        resp = httpx.get(
            robots_url,
            timeout=ROBOTS_TIMEOUT,
            # CR-01: sem seguir redirecionamento — o host da URL original ja
            # foi validado pelo chamador (buscar_html), mas um 3xx aqui
            # poderia apontar para um host privado que nunca passou por essa
            # validacao. Um robots.txt redirecionado e tratado como
            # ilegivel (fail-open ja documentado abaixo).
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
        )
        if resp.status_code >= 400:
            return True  # sem robots.txt legivel, assume que pode
        parser.parse(resp.text.splitlines())
    except Exception:
        return True
    return parser.can_fetch(USER_AGENT, url)


def buscar_html(url: str) -> str:
    """Baixa o HTML da pagina. Levanta FetchError em qualquer problema."""
    _validar_url_publica(url)

    if not pode_raspar(url):
        raise FetchError("O robots.txt do site nao permite acesso automatizado.")

    try:
        with httpx.Client(
            timeout=TIMEOUT,
            # CR-01: redirecionamento automatico desligado de proposito —
            # cada hop precisa ser revalidado contra endereco privado antes
            # de ser seguido, senao um servidor publico poderia
            # redirecionar para 169.254.169.254 ou para localhost.
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            redirecionamentos = 0
            resp = client.get(url)
            while resp.is_redirect:
                redirecionamentos += 1
                if redirecionamentos > MAX_REDIRECTS:
                    raise FetchError("Excesso de redirecionamentos.")
                destino = resp.headers.get("location")
                if not destino:
                    raise FetchError("Redirecionamento sem destino valido.")
                url = str(httpx.URL(url).join(destino))
                _validar_url_publica(url)
                resp = client.get(url)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise FetchError(f"O site respondeu {e.response.status_code}.") from e
    except httpx.RequestError as e:
        raise FetchError(f"Nao consegui alcancar o site: {type(e).__name__}") from e

    tipo = resp.headers.get("content-type", "")
    if "html" not in tipo:
        raise FetchError(f"O endereco nao devolveu HTML (veio {tipo or 'sem tipo'}).")

    if len(resp.content) > MAX_BYTES:
        raise FetchError("Pagina grande demais.")

    return resp.text


def extrair_texto(html: str) -> tuple[str, str]:
    """
    Transforma HTML em (titulo, texto limpo).

    Funcao pura: nao acessa rede. Da para testar com um HTML fixo.
    """
    soup = BeautifulSoup(html, "lxml")

    # Fora tudo que nunca contem informacao util para um vendedor.
    # ATENCAO: <footer> NAO entra nesta lista. O primeiro teste que escrevi
    # falhou por isso: e-mail e telefone de contato quase sempre moram no
    # rodape, e removendo o footer o extrator perdia justamente o dado mais
    # acionavel para o vendedor.
    for tag in soup(["script", "style", "nav", "noscript", "svg", "form"]):
        tag.decompose()

    titulo = soup.title.get_text(strip=True) if soup.title else ""

    texto = soup.get_text(separator="\n")
    linhas = [linha.strip() for linha in texto.splitlines()]
    # Linha com menos de 3 caracteres quase sempre e ruido de menu.
    linhas = [linha for linha in linhas if len(linha) > 2]
    return titulo, "\n".join(linhas)

