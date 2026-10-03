from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.ticket import Ticket
    from app.models.user import User


class Comment(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "comments"

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    ticket_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False)

    company: Mapped[Company] = relationship(back_populates="comments")
    ticket: Mapped[Ticket] = relationship(back_populates="comments")
    author: Mapped[User] = relationship(back_populates="comments")
