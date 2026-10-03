from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.ticket import Ticket


class Customer(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "external_reference",
            name="uq_customers_company_external_reference",
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    external_reference: Mapped[str | None] = mapped_column(String(255))

    company: Mapped[Company] = relationship(back_populates="customers")
    tickets: Mapped[list[Ticket]] = relationship(back_populates="requester")
