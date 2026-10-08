from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.models.enums import UserRole


password_hasher = PasswordHasher()


@dataclass(frozen=True)
class RequestIdentity:
    principal_type: str
    principal_id: UUID
    company_id: UUID
    role: UserRole | None = None


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def create_access_token(identity: RequestIdentity) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(identity.principal_id),
        "company_id": str(identity.company_id),
        "principal_type": identity.principal_type,
        "role": identity.role.value if identity.role else None,
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> RequestIdentity:
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "company_id", "principal_type", "type", "exp"]},
    )
    if payload.get("type") != "access":
        raise ValueError("Invalid access token type")

    role_value = payload.get("role")
    role = UserRole(role_value) if role_value else None
    return RequestIdentity(
        principal_type=str(payload["principal_type"]),
        principal_id=UUID(str(payload["sub"])),
        company_id=UUID(str(payload["company_id"])),
        role=role,
    )


def hash_api_key(api_key: str) -> str:
    return password_hasher.hash(api_key)


def verify_api_key(api_key: str, key_hash: str) -> bool:
    return verify_password(api_key, key_hash)
