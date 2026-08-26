"""
Busca a pagina e extrai o texto legivel.

Duas responsabilidades separadas de proposito:
  - buscar (rede, pode falhar, precisa de timeout)
  - extrair texto (puro, testavel sem internet)
"""

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


class FetchError(Exception):
    """Falha ao buscar a pagina. Guarda o motivo para mostrar ao vendedor."""


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
            follow_redirects=True,
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
    if not pode_raspar(url):
        raise FetchError("O robots.txt do site nao permite acesso automatizado.")

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

