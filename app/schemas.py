"""
Formato do briefing que a API devolve.

Este arquivo e o coracao do projeto. Ele define O QUE o vendedor recebe.
O scraping e o LLM sao meio; o briefing e o fim.

Campos escolhidos pensando na pergunta "o que eu preciso saber antes de
entrar numa reuniao com esse cliente?".
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class Briefing(BaseModel):
    """Resumo de uma empresa, pronto para o vendedor ler antes da reuniao."""

    empresa: str = Field(description="Nome da empresa")
    resumo: str = Field(description="O que a empresa faz, em 2 ou 3 frases")
    segmento: str | None = Field(default=None, description="Setor de atuacao")
    porte_estimado: str | None = Field(
        default=None, description="Indicio de tamanho: startup, media, grande"
    )
    produtos: list[str] = Field(
        default_factory=list, description="Produtos ou servicos oferecidos"
    )
    publico_alvo: str | None = Field(default=None, description="Para quem ela vende")
    sinais_recentes: list[str] = Field(
        default_factory=list,
        description="Novidades, lancamentos, expansao. Servem de gancho de conversa.",
    )
    dores_provaveis: list[str] = Field(
        default_factory=list,
        description="Hipoteses de problema que a bna.dev poderia resolver",
    )
    ganchos_de_conversa: list[str] = Field(
        default_factory=list, description="Frases que o vendedor pode usar para abrir"
    )
    contatos: list[str] = Field(
        default_factory=list, description="E-mails e telefones publicos encontrados"
    )
    confianca: Literal["alta", "media", "baixa"] = Field(
        default="media",
        description="Quanto o extrator confia no resultado. Baixa = pouco conteudo util.",
    )


class BriefingResponse(BaseModel):
    """O que a API devolve, com metadados de origem."""

    url: str
    briefing: Briefing
    origem: Literal["cache", "novo"] = Field(
        description="Se veio do banco (cache) ou foi raspado agora"
    )
    extrator: Literal["llm", "heuristico", "falha"] = Field(
        description="Qual implementacao gerou: heuristico, llm ou falha"
    )
    degradado: str | None = Field(
        default=None,
        description="Motivo da degradacao para o heuristico, quando o extrator principal falhou",
    )
    coletado_em: datetime


class BriefingRequest(BaseModel):
    """O que o vendedor envia."""

    urls: list[HttpUrl] = Field(min_length=1, max_length=10)
    forcar_atualizacao: bool = Field(
        default=False, description="Ignora o cache e raspa de novo"
    )


class LoginRequest(BaseModel):
    """O que o cliente envia para logar. Exatamente dois campos: `papel`
    nunca vem da requisicao (D-17), sempre e lido da linha de usuarios."""

    username: str = Field(min_length=1, max_length=64)
    senha: str = Field(
        min_length=1,
        max_length=128,
        description="Teto de 128: limite de custo contra forcar o KDF sobre um corpo gigante",
    )


class Usuario(BaseModel):
    """Formato do usuario devolvido pela API. Nunca carrega senha_hash nem
    nenhum campo derivado da senha."""

    id: str
    username: str
    papel: Literal["vendedor", "admin"]
    ativo: bool


class CriarUsuarioRequest(BaseModel):
    """O que o admin envia para cadastrar um vendedor ou outro admin.
    `papel` fecha a enumeracao de L-08 no proprio tipo — um papel inventado
    vira 422 antes de qualquer codigo de rota rodar."""

    username: str = Field(min_length=3, max_length=64)
    senha: str = Field(
        min_length=12,
        max_length=128,
        description="Mesmo minimo do seed de admin (D-19) — a politica de senha e uma so",
    )
    papel: Literal["vendedor", "admin"]


class AlterarAtivoRequest(BaseModel):
    """O que o admin envia para ativar/desativar um usuario. O id do alvo
    vem sempre do caminho da rota, nunca deste corpo."""

    ativo: bool

