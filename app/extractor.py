"""
Transforma texto bruto em Briefing estruturado.

DECISAO DE ARQUITETURA (a mais importante do projeto):
o extrator fica atras de uma interface. Existem duas implementacoes:

  - HeuristicExtractor: regras simples, sem custo, sem chave de API.
    Roda sempre. Serve de fallback quando o LLM falha ou estoura orcamento.
  - LLMExtractor: manda o texto para um modelo e exige saida estruturada
    validada pelo mesmo schema Pydantic.

Quem chama nao sabe qual esta rodando. Trocar um pelo outro nao altera
nenhuma outra parte do sistema.

Isso resolve tres problemas de uma vez:
  1. o sistema funciona antes de existir chave de API;
  2. se o LLM cair ou o custo estourar, tem para onde degradar;
  3. da para comparar as duas saidas e medir se o LLM realmente melhora.
"""

import os
import re
from typing import Protocol

from .schemas import Briefing

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
TEL_RE = re.compile(r"\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}")


class Extractor(Protocol):
    """Contrato que qualquer extrator precisa cumprir."""

    nome: str

    def extrair(self, url: str, titulo: str, texto: str) -> Briefing: ...


class HeuristicExtractor:
    """
    Extrator sem IA. Nao entende o conteudo, so organiza o que da para
    identificar por regra. Confianca sempre baixa, e isso e honesto:
    ele nao sabe o que a empresa faz, so recorta o comeco do texto.
    """

    nome = "heuristico"

    def extrair(self, url: str, titulo: str, texto: str) -> Briefing:
        empresa = titulo.split("|")[0].split("-")[0].strip() or url

        paragrafos = [p for p in texto.split("\n") if len(p) > 60]
        resumo = " ".join(paragrafos[:2])[:400] if paragrafos else "Sem texto suficiente."

        contatos = sorted(set(EMAIL_RE.findall(texto)) | set(TEL_RE.findall(texto)))

        return Briefing(
            empresa=empresa,
            resumo=resumo,
            contatos=contatos[:5],
            confianca="baixa",
        )


class LLMExtractor:
    """
    Extrator com LLM. Manda o texto e exige de volta um JSON no formato
    do schema Briefing. A validacao do Pydantic e a rede de seguranca:
    se o modelo devolver algo fora do formato, levanta erro em vez de
    entregar lixo para o vendedor.

    Ainda nao ligado: aguardando chave de API.
    """

    nome = "llm"

    def __init__(self, api_key: str | None = None, modelo: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.modelo = modelo

    def disponivel(self) -> bool:
        return bool(self.api_key)

    def extrair(self, url: str, titulo: str, texto: str) -> Briefing:
        if not self.disponivel():
            raise RuntimeError("Sem chave de API configurada.")
        # Corte de custo: texto longo demais nao melhora o resultado e
        # multiplica o preco por chamada.
        _trecho = texto[:12000]
        raise NotImplementedError("Chamada ao LLM entra quando a chave chegar.")


def escolher_extrator() -> Extractor:
    """
    Usa o LLM se houver chave, senao cai no heuristico.
    Degradacao graciosa: o sistema nunca fica fora do ar por falta de IA.
    """
    llm = LLMExtractor()
    if llm.disponivel():
        return llm
    return HeuristicExtractor()

