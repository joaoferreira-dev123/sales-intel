"""
Configuracao lida do ambiente.

Por D-04 emendada, so as quatro variaveis do LLM saem para o ambiente nesta
fase: as demais (timeout do fetch, validade do cache, user-agent, banco,
debug) pertencem a fases ja entregues e testadas, e move-las agora e
superficie de regressao sem retorno de demonstracao.

`llm_api_key()` le a variavel a cada chamada, nunca no import, porque os
testes trocam `LLM_API_KEY` via `monkeypatch.setenv`/`delenv` em tempo de
execucao — uma constante congelada no import nao veria a troca.

Por D-13, o endpoint e o modelo tambem viram variaveis de ambiente: a conta
em uso e de um provedor compativel com a API da OpenAI, mas nao e a OpenAI, e
os padroes abaixo apontam para esse provedor real justamente para que
exportar so a chave ja funcione de ponta a ponta.

Por D-19, `admin_username()` e `admin_senha()` semeiam o primeiro
administrador na subida do processo e nunca tem valor padrao.
"""

import os


def llm_api_key() -> str | None:
    """Funcao, nao constante: precisa ler o ambiente em tempo de chamada
    para que o monkeypatch dos testes 1 e 2 (plano 03) funcione."""
    return os.getenv("LLM_API_KEY") or None


def admin_username() -> str | None:
    """Funcao, nao constante (D-19): o seed de bootstrap e os testes do
    plano 06-04 trocam o ambiente em tempo de execucao."""
    return os.getenv("ADMIN_USERNAME") or None


def admin_senha() -> str | None:
    """Funcao, nao constante (D-19): o seed de bootstrap e os testes do
    plano 06-04 trocam o ambiente em tempo de execucao."""
    return os.getenv("ADMIN_SENHA") or None


# Modelo padrao: unico modelo grande da conta em uso com saida estruturada
# nativa (D-14), o que o caminho primario de D-02 exige. Diverge do padrao
# da SPEC S13 (gpt-4o-mini) de proposito — D-13 invertida: um modelo que nao
# existe no provedor padrao daria 400/404 e degradaria em silencio, movendo
# a armadilha em vez de fecha-la.
LLM_MODELO = os.getenv("LLM_MODELO", "openai/gpt-oss-120b")

# Corte de custo (L-04, SPEC S11): texto mais longo nao melhora o resultado
# e multiplica o preco por chamada.
LLM_MAX_CHARS = int(os.getenv("LLM_MAX_CHARS", "12000"))

# Endpoint do provedor: qualquer endereco compativel com a API da OpenAI
# serve, entao trocar de provedor e trocar o .env, nao o codigo (SPEC S7
# item 4). O padrao aponta para o endereco do provedor da chave em uso e
# forma par com LLM_MODELO acima: as duas linhas mudam juntas ou nenhuma
# muda, e e assim que D-13 faz com que exportar so LLM_API_KEY ja funcione.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
