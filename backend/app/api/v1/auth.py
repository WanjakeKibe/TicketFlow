from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentIdentity, authentication_error
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.services.auth import (
    authenticate_user,
    issue_user_access_token,
    register_company_owner,
)


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    try:
        user = register_company_owner(db, request)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create company",
        ) from None

    settings = get_settings()
    return AuthResponse(
        access_token=issue_user_access_token(user),
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user, from_attributes=True),
    )


@router.post("/login", response_model=AuthResponse)
def login(
    request: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    user = authenticate_user(db, str(request.email), request.password)
    if user is None:
        raise authentication_error()

    settings = get_settings()
    return AuthResponse(
        access_token=issue_user_access_token(user),
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user, from_attributes=True),
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    identity: CurrentIdentity,
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    from sqlalchemy import select

    from app.models import User

    user = db.scalar(
        select(User).where(
            User.id == identity.principal_id,
            User.company_id == identity.company_id,
        )
    )
    if user is None:
        raise authentication_error()
    return UserResponse.model_validate(user, from_attributes=True)
