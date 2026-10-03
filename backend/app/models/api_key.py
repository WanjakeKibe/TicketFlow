from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.company import Company


class ApiKey(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint(
        "company_id", "key_hash", name="uq_api_keys_company_hash"),)

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True))

    company: Mapped[Company] = relationship(back_populates="api_keys")
