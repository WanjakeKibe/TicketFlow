from __future__ import annotations

from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    RequestIdentity,
    decode_access_token,
    verify_api_key,
)
from app.db.session import get_db
from app.models import ApiKey, User, UserRole
from app.models.common import utc_now


bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_identity(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> RequestIdentity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise authentication_error()

    try:
        identity = decode_access_token(credentials.credentials)
    except (ValueError, jwt.InvalidTokenError):
        raise authentication_error() from None

    if identity.principal_type != "user":
        raise authentication_error()

    user = db.scalar(
        select(User).where(
            User.id == identity.principal_id,
            User.company_id == identity.company_id,
        )
    )
    if user is None or not user.is_active:
        raise authentication_error()

    return RequestIdentity(
        principal_type="user",
        principal_id=user.id,
        company_id=user.company_id,
        role=user.role,
    )


CurrentIdentity = Annotated[RequestIdentity, Depends(get_current_identity)]


def get_api_key_identity(
    api_key: Annotated[str | None, Depends(api_key_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> RequestIdentity:
    if not api_key or not api_key.startswith("tfk_"):
        raise authentication_error()

    try:
        api_key_id = UUID(api_key.split("_", 2)[1])
    except (IndexError, ValueError):
        raise authentication_error() from None

    stored_key = db.scalar(select(ApiKey).where(ApiKey.id == api_key_id))
    if (
        stored_key is None
        or stored_key.revoked_at is not None
        or not verify_api_key(api_key, stored_key.key_hash)
    ):
        raise authentication_error()

    stored_key.last_used_at = utc_now()
    db.commit()
    return RequestIdentity(
        principal_type="api_key",
        principal_id=stored_key.id,
        company_id=stored_key.company_id,
    )


ApiKeyIdentity = Annotated[RequestIdentity, Depends(get_api_key_identity)]


def require_owner(identity: CurrentIdentity) -> RequestIdentity:
    if identity.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner permission required",
        )
    return identity


OwnerIdentity = Annotated[RequestIdentity, Depends(require_owner)]
