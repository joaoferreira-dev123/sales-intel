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
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path("briefings.db")
VALIDADE = timedelta(days=7)  # depois disso, considera desatualizado


def conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def criar_tabelas() -> None:
    # WR-02: `with conectar() as conn` sozinho so commita/reverte a
    # transacao — nao fecha a conexao nem o file handle. `closing()` garante
    # o fechamento explicito; o `conn` interno segue fazendo commit/rollback.
    with closing(conectar()) as conn, conn:
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
        # Fase 6 (D-15/D-16): usuarios e sessoes, criadas aqui pelo mesmo
        # molde de briefings acima. "username" e UNIQUE por restricao de
        # banco (SPEC S8), nao so checagem em Python.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id         TEXT PRIMARY KEY,
                username   TEXT NOT NULL UNIQUE,
                senha_hash TEXT NOT NULL,
                papel      TEXT NOT NULL,
                ativo      INTEGER NOT NULL DEFAULT 1,
                criado_em  TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessoes (
                token_hash TEXT PRIMARY KEY,
                usuario_id TEXT NOT NULL,
                criada_em  TEXT NOT NULL,
                expira_em  TEXT NOT NULL
            )
            """
        )
        # Fase 6 (D-18): `briefings` ganha um dono, mas so de forma aditiva.
        # SQLite nao tem "ADD COLUMN IF NOT EXISTS" — a checagem via
        # PRAGMA e o que torna esta chamada repetivel sem erro. Nenhuma
        # linha ja gravada e tocada: a coluna nasce nula em toda linha
        # anterior a Fase 6, e e a leitura (listar, abaixo) que decide o
        # que aparece para quem, nunca uma migracao que reescreva ou
        # apague dado velho (D-18, herdado de D-09/D-10 em buscar() e do
        # aceite T-05-36).
        colunas_briefings = {
            row["name"] for row in conn.execute("PRAGMA table_info(briefings)").fetchall()
        }
        if "owner" not in colunas_briefings:
            conn.execute("ALTER TABLE briefings ADD COLUMN owner TEXT")


def buscar(url: str, llm_disponivel: bool = False) -> tuple[dict, str, datetime] | None:
    """
    Devolve (briefing, extrator, data) se houver cache valido. Quando o LLM
    esta disponivel, uma entrada gravada pelo heuristico e tratada como
    ausente (D-09).
    """
    with closing(conectar()) as conn, conn:
        row = conn.execute(
            "SELECT briefing, extrator, coletado_em FROM briefings WHERE url = ?",
            (url,),
        ).fetchone()

    if row is None:
        return None

    # WR-03: uma linha corrompida (data ou JSON ilegivel) e dado velho, nao
    # erro do usuario — mesma politica de "linha ruim = cache miss, recolete"
    # que ja vale para drift de schema (D-10) em app/main.py. Sem esta
    # captura, `datetime.fromisoformat`/`json.loads` levantavam direto para
    # o `except Exception` largo de main.py, que produzia um briefing
    # "falha" terminal em vez de recoletar.
    try:
        coletado_em = datetime.fromisoformat(row["coletado_em"])
    except ValueError:
        return None

    if datetime.now(timezone.utc) - coletado_em > VALIDADE:
        return None  # existe, mas venceu

    if llm_disponivel and row["extrator"] == "heuristico":
        return None  # heuristico com LLM ligado: forca recoleta para subir a qualidade

    try:
        briefing = json.loads(row["briefing"])
    except json.JSONDecodeError:
        return None

    return briefing, row["extrator"], coletado_em


def salvar(url: str, briefing: dict, extrator: str, dono: str | None = None) -> datetime:
    agora = datetime.now(timezone.utc)
    with closing(conectar()) as conn, conn:
        conn.execute(
            """
            INSERT INTO briefings (url, briefing, extrator, coletado_em, owner)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                briefing = excluded.briefing,
                extrator = excluded.extrator,
                coletado_em = excluded.coletado_em
            """,
            # D-18: a clausula de conflito acima nao inclui `owner` de
            # proposito. `briefings` guarda uma linha por URL desde a Fase 3
            # (cache compartilhado); uma recoleta por outro vendedor deve
            # atualizar o conteudo, mas transferir a procedencia seria
            # roubar a linha de quem coletou primeiro. O primeiro coletor
            # fica com a linha.
            (url, json.dumps(briefing, ensure_ascii=False), extrator, agora.isoformat(), dono),
        )
    return agora


def listar(limite: int = 50, dono: str | None = None, ver_tudo: bool = False) -> list[dict]:
    """Historico de briefings. D-18: a regra de visibilidade vive aqui, na
    leitura — nunca na escrita, nunca numa migracao. `ver_tudo=True` e a
    visao do admin (todas as linhas, inclusive as de dono nulo); `dono`
    filtra pela coluna `owner`, e nunca casa com linha de dono nulo."""
    with closing(conectar()) as conn, conn:
        if ver_tudo:
            rows = conn.execute(
                """
                SELECT briefings.url AS url, briefings.extrator AS extrator,
                       briefings.coletado_em AS coletado_em, usuarios.username AS dono
                FROM briefings
                LEFT JOIN usuarios ON usuarios.id = briefings.owner
                ORDER BY briefings.coletado_em DESC
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
        elif dono:
            rows = conn.execute(
                """
                SELECT briefings.url AS url, briefings.extrator AS extrator,
                       briefings.coletado_em AS coletado_em, usuarios.username AS dono
                FROM briefings
                LEFT JOIN usuarios ON usuarios.id = briefings.owner
                WHERE briefings.owner = ?
                ORDER BY briefings.coletado_em DESC
                LIMIT ?
                """,
                (dono, limite),
            ).fetchall()
        else:
            # D-18: ramo deliberadamente fail-closed. Um chamador que
            # esqueca de passar `dono` ou `ver_tudo` recebe lista vazia,
            # nunca a tabela inteira.
            return []
    return [dict(r) for r in rows]

