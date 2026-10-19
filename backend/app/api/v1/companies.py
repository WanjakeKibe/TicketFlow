from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.dependencies import (
    CurrentIdentity,
    authorize_roles,
)
from app.core.api_errors import api_error, documented_errors
from app.core.config import get_settings
from app.db.session import get_db
from app.models import UserRole
from app.schemas.auth import AuthResponse, UserResponse
from app.schemas.company import (
    CompanyResponse,
    CompanyUsersResponse,
    CreateCompanyRequest,
)
from app.services.auth import issue_user_access_token, register_company_owner
from app.services.companies import get_company_for_identity, list_company_users


router = APIRouter(
    prefix="/companies",
    tags=["companies"],
    responses=documented_errors(401, 403, 404, 409, 422, 500),
)


@router.post(
    "",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_company(
    request: CreateCompanyRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    try:
        owner = register_company_owner(db, request)
    except IntegrityError:
        db.rollback()
        raise api_error(
            status.HTTP_409_CONFLICT, "RESOURCE_CONFLICT", "Unable to create company"
        ) from None

    settings = get_settings()
    return AuthResponse(
        access_token=issue_user_access_token(owner),
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(owner, from_attributes=True),
    )


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: UUID,
    identity: CurrentIdentity,
    db: Annotated[Session, Depends(get_db)],
) -> CompanyResponse:
    company = get_company_for_identity(db, company_id, identity)
    if company is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND, "RESOURCE_NOT_FOUND", "Company was not found"
        )
    return CompanyResponse.model_validate(company, from_attributes=True)


@router.get("/{company_id}/users", response_model=CompanyUsersResponse)
def get_company_users(
    company_id: UUID,
    identity: CurrentIdentity,
    db: Annotated[Session, Depends(get_db)],
) -> CompanyUsersResponse:
    company = get_company_for_identity(db, company_id, identity)
    if company is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND, "RESOURCE_NOT_FOUND", "Company was not found"
        )
    authorize_roles(identity, UserRole.OWNER, UserRole.MANAGER)
    users = list_company_users(db, company.id)
    return CompanyUsersResponse(
        items=[
            UserResponse.model_validate(user, from_attributes=True)
            for user in users
        ],
        total=len(users),
    )
