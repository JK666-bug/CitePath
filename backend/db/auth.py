import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from pymysql.err import IntegrityError

from db.connection import connect

SESSION_DAYS = 14


def register_user(username: str, password: str) -> dict:
    name = _username(username)
    _password(password)
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (name, hash_password(password)),
            )
            user_id = cursor.lastrowid
        connection.commit()
    except IntegrityError as error:
        connection.rollback()
        raise ValueError("This username is already taken") from error
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {"id": user_id, "username": name}


def authenticate(username: str, password: str) -> dict | None:
    name = username.strip()
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, password_hash FROM users WHERE username = %s",
                (name,),
            )
            row = cursor.fetchone()
    finally:
        connection.close()
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "username": row["username"]}


def open_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(days=SESSION_DAYS)
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM login_sessions WHERE user_id = %s AND expires_at < NOW()",
                (user_id,),
            )
            cursor.execute(
                """
                INSERT INTO login_sessions (user_id, token, expires_at)
                VALUES (%s, %s, %s)
                """,
                (user_id, token, expires),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return token


def close_session(token: str | None) -> None:
    if not token:
        return
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM login_sessions WHERE token = %s", (token,))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def user_from_token(token: str | None) -> dict | None:
    if not token:
        return None
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.username, s.expires_at
                FROM login_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token = %s
                """,
                (token,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            if row["expires_at"] <= datetime.now():
                cursor.execute("DELETE FROM login_sessions WHERE token = %s", (token,))
                connection.commit()
                return None
    finally:
        connection.close()
    return {"id": row["id"], "username": row["username"]}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return f"pbkdf2_sha256$200000${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, rounds, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(rounds)
        ).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(check, digest)


def _username(value: str) -> str:
    name = value.strip()
    if len(name) < 2 or len(name) > 32:
        raise ValueError("Username must be 2 to 32 characters")
    if any(char.isspace() for char in name):
        raise ValueError("Username cannot contain spaces")
    return name


def _password(password: str) -> None:
    if len(password) < 6 or len(password) > 72:
        raise ValueError("Password must be 6 to 72 characters")
