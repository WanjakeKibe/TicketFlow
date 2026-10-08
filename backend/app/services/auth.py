from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    RequestIdentity,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models import Company, User, UserRole
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
