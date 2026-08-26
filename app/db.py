"""
Cache dos briefings ja gerados (o bonus 1 do case).

Antes de raspar, consulta aqui. Se ja existe e esta fresco, devolve o JSON
salvo. Economiza tempo, evita bater no site de novo e corta custo de LLM.

Usando SQLite para o prototipo: zero configuracao, roda em qualquer maquina.
Em producao vira PostgreSQL trocando so este arquivo, porque o resto do
sistema fala com as funcoes daqui, nao com o banco direto.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path("briefings.db")
VALIDADE = timedelta(days=7)  # depois disso, considera desatualizado


def conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def criar_tabelas() -> None:
    with conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS briefings (
                url         TEXT PRIMARY KEY,
                briefing    TEXT NOT NULL,
                extrator    TEXT NOT NULL,
                coletado_em TEXT NOT NULL
            )
            """
        )


def buscar(url: str, llm_disponivel: bool = False) -> tuple[dict, str, datetime] | None:
    """
    Devolve (briefing, extrator, data) se houver cache valido. Quando o LLM
    esta disponivel, uma entrada gravada pelo heuristico e tratada como
    ausente (D-09).
    """
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

    if llm_disponivel and row["extrator"] == "heuristico":
        return None  # heuristico com LLM ligado: forca recoleta para subir a qualidade

    return json.loads(row["briefing"]), row["extrator"], coletado_em


def salvar(url: str, briefing: dict, extrator: str) -> datetime:
    agora = datetime.now(timezone.utc)
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO briefings (url, briefing, extrator, coletado_em)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                briefing = excluded.briefing,
                extrator = excluded.extrator,
                coletado_em = excluded.coletado_em
            """,
            (url, json.dumps(briefing, ensure_ascii=False), extrator, agora.isoformat()),
        )
    return agora


def listar(limite: int = 50) -> list[dict]:
    """Historico para a tela de admin."""
    with conectar() as conn:
        rows = conn.execute(
            "SELECT url, extrator, coletado_em FROM briefings "
            "ORDER BY coletado_em DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [dict(r) for r in rows]

