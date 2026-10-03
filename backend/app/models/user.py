from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.company import Company
    from app.models.ticket import Ticket
    from app.models.ticket_event import TicketEvent


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint(
        "company_id", "email", name="uq_users_company_email"),)

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False)

    company: Mapped[Company] = relationship(back_populates="users")
    assigned_tickets: Mapped[list[Ticket]] = relationship(
        back_populates="assignee")
    comments: Mapped[list[Comment]] = relationship(back_populates="author")
    ticket_events: Mapped[list[TicketEvent]
                          ] = relationship(back_populates="actor")
