from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import RequestIdentity, decode_access_token
from app.db.session import get_db
from app.models import User


bearer_scheme = HTTPBearer(auto_error=False)


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
