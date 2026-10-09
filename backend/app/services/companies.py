from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import RequestIdentity
from app.models import Company, User


def get_company_for_identity(
    db: Session,
    company_id: UUID,
    identity: RequestIdentity,
) -> Company | None:
    if company_id != identity.company_id:
        return None
    return db.scalar(select(Company).where(Company.id == company_id))


def list_company_users(
    db: Session,
    company_id: UUID,
) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.company_id == company_id)
            .order_by(User.created_at, User.id)
        )
    )
