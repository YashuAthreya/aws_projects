# app/auth/security.py

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    try:
        return password_hasher.verify(
            password_hash,
            password,
        )
    except VerifyMismatchError:
        return False


def generate_session_token() -> str:
    """
    Generates a cryptographically secure opaque token.
    """
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    """
    Only the hash is stored in PostgreSQL.
    """
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()