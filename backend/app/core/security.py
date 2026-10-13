"""Password hashing (Argon2), JWT access tokens and constant-time API key comparison."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.exceptions import AuthenticationError

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)


def create_access_token(
    subject: str,
    *,
    secret: str,
    algorithm: str,
    expires_minutes: int,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "type": "access",
        **(extra_claims or {}),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(token: str, *, secret: str, algorithm: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, secret, algorithms=[algorithm], options={"require": ["sub", "exp", "iat"]}
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Session expirée, reconnectez-vous") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Jeton d'authentification invalide") from exc
    if payload.get("type") != "access":
        raise AuthenticationError("Type de jeton invalide")
    return payload


def api_keys_match(provided: str | None, expected: str) -> bool:
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided.encode(), expected.encode())
