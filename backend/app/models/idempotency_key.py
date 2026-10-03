from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.ticket import Ticket


class IdempotencyKey(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("company_id", "key",
                      name="uq_idempotency_company_key"),)

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSON, nullable=False)
    ticket_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)

    company: Mapped[Company] = relationship(back_populates="idempotency_keys")
    ticket: Mapped[Ticket | None] = relationship(
        back_populates="idempotency_keys")
