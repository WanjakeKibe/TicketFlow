from __future__ import annotations

import secrets
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    RequestIdentity,
    create_access_token,
    hash_api_key,
    hash_password,
    verify_password,
)
from app.models import ApiKey, Company, User, UserRole
from app.models.common import utc_now
from app.schemas.auth import RegisterRequest


def register_company_owner(db: Session, request: RegisterRequest) -> User:
    company = Company(name=request.company_name)
    owner = User(
        company=company,
        email=str(request.email).lower(),
        password_hash=hash_password(request.password),
        role=UserRole.OWNER,
        is_active=True,
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    statement = select(User).where(User.email == email.lower())
    user = db.scalar(statement)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def issue_user_access_token(user: User) -> str:
    return create_access_token(
        RequestIdentity(
            principal_type="user",
            principal_id=user.id,
            company_id=user.company_id,
            role=user.role,
        )
    )


def create_company_api_key(
    db: Session,
    company_id: UUID,
    name: str,
) -> tuple[ApiKey, str]:
    api_key_id = uuid4()
    raw_key = f"tfk_{api_key_id.hex}_{secrets.token_urlsafe(32)}"
    api_key = ApiKey(
        id=api_key_id,
        company_id=company_id,
        key_hash=hash_api_key(raw_key),
        name=name.strip(),
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key, raw_key


def revoke_company_api_key(
    db: Session,
    company_id: UUID,
    api_key_id: UUID,
) -> ApiKey | None:
    api_key = db.scalar(
        select(ApiKey).where(
            ApiKey.id == api_key_id,
            ApiKey.company_id == company_id,
        )
    )
    if api_key is None:
        return None
    if api_key.revoked_at is None:
        api_key.revoked_at = utc_now()
        db.commit()
        db.refresh(api_key)
    return api_key
