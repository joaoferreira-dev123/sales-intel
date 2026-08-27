"""
Autenticacao e autorizacao (Bonus 2 do case).

Duas decisoes divergem da SPEC original, ambas travadas pelo usuario em
2026-08-27 e registradas em `.planning/phases/06-auth/06-CONTEXT.md`:

- D-15: hash de senha com `hashlib.scrypt` da stdlib, nao argon2. A SPEC S8
  pede argon2, mas `argon2-cffi` e pacote novo com extensao C compilada, e
  L-06 proibe dependencia nova antes da entrega. `scrypt` e KDF memory-hard,
  esta na stdlib, e nao arrisca falhar o build em maquina limpa.
- D-16: sessao como token opaco (`secrets.token_urlsafe`) gravado numa
  tabela SQLite, nao JWT nem cookie assinado a mao. Nenhum pacote de JWT
  esta instalado, e L-06 proibe instalar; assinar cookie a mao com `hmac`
  seria cripto escrita as pressas na vespera da entrega. Guardar sessao no
  banco e estritamente mais simples e casa com L-09 (SQLite continua):
  revogar sessao vira um `DELETE`.
"""

import base64
import hashlib
import hmac
import secrets
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone

from . import config, db

# Parametros de D-15. Nao reduzir para acelerar a suite de teste — o
# criterio de aceite do plano trava estes quatro valores.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
TAM_SALT = 16

DURACAO_SESSAO = timedelta(hours=12)
NOME_COOKIE_SESSAO = "sessao"

# L-02/D-06: literal autorado unico, usado tanto para usuario inexistente
# quanto para senha errada. A frase e deliberadamente identica nos dois
# casos para nao revelar, pela resposta, quais usernames existem (T-06-01).
MSG_LOGIN_INVALIDO = "Usuario ou senha invalidos."

# D-19: mesmo minimo exigido pelo schema de criacao de usuario (Task 2) — a
# politica de senha e uma so, nao duas.
TAM_MINIMO_SENHA = 12
MSG_SENHA_DE_ADMIN_CURTA = (
    f"ADMIN_SENHA precisa ter pelo menos {TAM_MINIMO_SENHA} caracteres."
)


def gerar_hash_senha(senha: str) -> str:
    """Devolve string autodescritiva scrypt$n$r$p$salt$hash (D-15). Os
    parametros viajam dentro da string para que um aumento futuro de custo
    nao invalide hash ja gravado."""
    salt = secrets.token_bytes(TAM_SALT)
    chave = hashlib.scrypt(
        senha.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    chave_b64 = base64.urlsafe_b64encode(chave).decode("ascii")
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt_b64}${chave_b64}"


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """Compara em tempo constante via hmac.compare_digest (D-15). Um hash
    malformado devolve False em vez de levantar."""
    try:
        algoritmo, n_str, r_str, p_str, salt_b64, chave_b64 = hash_armazenado.split("$")
        if algoritmo != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_b64)
        chave_esperada = base64.urlsafe_b64decode(chave_b64)
        chave_calculada = hashlib.scrypt(
            senha.encode("utf-8"),
            salt=salt,
            n=int(n_str),
            r=int(r_str),
            p=int(p_str),
            dklen=len(chave_esperada),
        )
    except (ValueError, TypeError):
        return False

    # Comparacao em tempo constante de proposito: uma comparacao normal (==)
    # vaza, pelo tempo de resposta, em qual byte a chave calculada diverge
    # da esperada (T-06-11).
    return hmac.compare_digest(chave_calculada, chave_esperada)


# Equaliza o tempo de resposta quando o username nao existe: o mesmo
# trabalho de KDF acontece nos dois caminhos de `autenticar` (T-06-02).
# Nunca e uma senha literal escrita no arquivo — e gerada uma vez, no
# import, a partir de um token aleatorio descartado.
_HASH_DUMMY = gerar_hash_senha(secrets.token_urlsafe(32))


def criar_usuario(username: str, senha: str, papel: str) -> dict:
    """Cria um usuario novo e devolve o dict do usuario, sem o hash da
    senha. Username duplicado levanta ValueError com frase autorada."""
    usuario_id = str(uuid.uuid4())
    senha_hash = gerar_hash_senha(senha)
    criado_em = datetime.now(timezone.utc).isoformat()
    try:
        with closing(db.conectar()) as conn, conn:
            conn.execute(
                """
                INSERT INTO usuarios (id, username, senha_hash, papel, ativo, criado_em)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (usuario_id, username, senha_hash, papel, criado_em),
            )
    except sqlite3.IntegrityError as e:
        # Nao deixa o erro cru do SQLite subir para uma rota (D-06).
        raise ValueError(f"Ja existe um usuario com o username '{username}'.") from e

    return {
        "id": usuario_id,
        "username": username,
        "papel": papel,
        "ativo": True,
    }


def buscar_usuario_por_id(usuario_id: str) -> dict | None:
    """Devolve o dict do usuario (com senha_hash) ou None."""
    with closing(db.conectar()) as conn, conn:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE id = ?",
            (usuario_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def buscar_usuario_por_username(username: str) -> dict | None:
    """Devolve o dict do usuario (com senha_hash) ou None."""
    with closing(db.conectar()) as conn, conn:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row is not None else None


def listar_usuarios() -> list[dict]:
    """Tela de admin: lista de usuarios sem nenhum campo derivado de
    senha."""
    with closing(db.conectar()) as conn, conn:
        rows = conn.execute(
            "SELECT id, username, papel, ativo FROM usuarios ORDER BY criado_em"
        ).fetchall()
    return [dict(r) for r in rows]


def autenticar(username: str, senha: str) -> dict | None:
    """Autentica por username e senha. Devolve o dict do usuario (sem
    senha_hash) ou None — nunca um motivo diferente para cada caso, para
    nao distinguir usuario inexistente de senha errada (D-15)."""
    usuario = buscar_usuario_por_username(username)
    if usuario is None:
        # Defesa de timing (T-06-02): o mesmo trabalho de KDF acontece aqui
        # quanto no caminho de usuario existente, contra o hash dummy.
        verificar_senha(senha, _HASH_DUMMY)
        return None

    if not usuario["ativo"]:
        return None

    if not verificar_senha(senha, usuario["senha_hash"]):
        return None

    return {
        "id": usuario["id"],
        "username": usuario["username"],
        "papel": usuario["papel"],
        "ativo": bool(usuario["ativo"]),
    }


def criar_sessao(usuario_id: str) -> str:
    """Cria uma sessao nova e devolve o token bruto, que so existe no
    cookie — o banco guarda apenas o digest sha256 (D-16 endurecido)."""
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    agora = datetime.now(timezone.utc)
    expira_em = agora + DURACAO_SESSAO
    with closing(db.conectar()) as conn, conn:
        conn.execute(
            """
            INSERT INTO sessoes (token_hash, usuario_id, criada_em, expira_em)
            VALUES (?, ?, ?, ?)
            """,
            (token_hash, usuario_id, agora.isoformat(), expira_em.isoformat()),
        )
    return token


def validar_sessao(token: str) -> dict | None:
    """Devolve o dict do usuario dono da sessao, quando a sessao existe,
    ainda nao expirou e o usuario esta ativo. Sessao expirada e removida
    nesta mesma chamada. Nunca devolve o hash da senha."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with closing(db.conectar()) as conn, conn:
        row = conn.execute(
            """
            SELECT sessoes.expira_em AS expira_em, usuarios.id AS id,
                   usuarios.username AS username, usuarios.papel AS papel,
                   usuarios.ativo AS ativo
            FROM sessoes
            JOIN usuarios ON usuarios.id = sessoes.usuario_id
            WHERE sessoes.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()

        if row is None:
            return None

        expira_em = datetime.fromisoformat(row["expira_em"])
        if datetime.now(timezone.utc) > expira_em:
            conn.execute("DELETE FROM sessoes WHERE token_hash = ?", (token_hash,))
            return None

        if not row["ativo"]:
            return None

        return {
            "id": row["id"],
            "username": row["username"],
            "papel": row["papel"],
            "ativo": bool(row["ativo"]),
        }


def encerrar_sessao(token: str) -> None:
    """Remove a sessao correspondente ao token. Sessao ja inexistente
    (segunda chamada, token invalido) nao levanta erro."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with closing(db.conectar()) as conn, conn:
        conn.execute("DELETE FROM sessoes WHERE token_hash = ?", (token_hash,))


def semear_admin_inicial() -> str | None:
    """Semeia o primeiro administrador a partir do ambiente (D-19). Chamada
    por `inicializar()` logo apos `db.criar_tabelas()` — e o unico gancho de
    subida que o projeto tem.

    Ordem deliberada:
    1. Sem as duas variaveis (ou so uma delas), devolve None sem criar nada
       e sem levantar. O processo precisa subir mesmo sem administrador,
       senao ate a rota de saude deixaria de responder numa maquina limpa.
    2. Senha curta levanta, nao semeia em silencio: quem definiu as duas
       variaveis quer um administrador, e semear credencial fraca ou nao
       semear em silencio sao os dois piores desfechos. Nenhum usuario final
       consegue disparar este caminho, porque as duas variaveis so entram
       pelo ambiente do processo, nunca por uma requisicao.
    3. Username ja existente: devolve None sem tocar em nada. Trocar a senha
       faria um restart desfazer uma rotacao; promover o usuario a admin
       daria a quem controla o ambiente um caminho de escalada que nao passa
       pela rota de admin (Task 2).
    4. Caso contrario, cria o usuario com papel de administrador.
    """
    username = config.admin_username()
    senha = config.admin_senha()
    if not username or not senha:
        return None

    if len(senha) < TAM_MINIMO_SENHA:
        raise RuntimeError(MSG_SENHA_DE_ADMIN_CURTA)

    if buscar_usuario_por_username(username) is not None:
        return None

    usuario = criar_usuario(username, senha, "admin")
    return usuario["id"]


def encerrar_sessoes_do_usuario(usuario_id: str) -> int:
    """Remove todas as sessoes daquele usuario e devolve quantas foram
    removidas. Usada por `definir_ativo` no caminho de desativacao."""
    with closing(db.conectar()) as conn, conn:
        cursor = conn.execute(
            "DELETE FROM sessoes WHERE usuario_id = ?", (usuario_id,)
        )
        return cursor.rowcount


def definir_ativo(usuario_id: str, ativo: bool) -> dict | None:
    """Atualiza a coluna `ativo` do usuario e devolve o dict atualizado, ou
    None se o id nao existe. Quando `ativo` e falso, encerra na mesma
    operacao todas as sessoes vivas do usuario: mudar so a coluna sem
    apagar a sessao deixaria o usuario desativado navegando ate a sessao
    expirar sozinha, e revogacao imediata e justamente o que D-16 comprou
    ao guardar sessao em tabela."""
    if buscar_usuario_por_id(usuario_id) is None:
        return None

    with closing(db.conectar()) as conn, conn:
        conn.execute(
            "UPDATE usuarios SET ativo = ? WHERE id = ?",
            (1 if ativo else 0, usuario_id),
        )

    if not ativo:
        encerrar_sessoes_do_usuario(usuario_id)

    usuario = buscar_usuario_por_id(usuario_id)
    return {
        "id": usuario["id"],
        "username": usuario["username"],
        "papel": usuario["papel"],
        "ativo": bool(usuario["ativo"]),
    }
