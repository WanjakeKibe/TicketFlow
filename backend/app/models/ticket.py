from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TicketPriority, TicketStatus

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.company import Company
    from app.models.customer import Customer
    from app.models.idempotency_key import IdempotencyKey
    from app.models.ticket_event import TicketEvent
    from app.models.user import User


class Ticket(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("company_id", "public_id",
                         name="uq_tickets_company_public_id"),
        Index("ix_tickets_company_created_at", "company_id", "created_at"),
        Index("ix_tickets_company_status", "company_id", "status"),
        Index("ix_tickets_company_priority", "company_id", "priority"),
        Index("ix_tickets_company_assignee", "company_id", "assignee_id"),
        Index("ix_tickets_company_requester", "company_id", "requester_id"),
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    public_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), default=uuid4, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status"), default=TicketStatus.OPEN, nullable=False
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticket_priority"),
        default=TicketPriority.NORMAL,
        nullable=False,
    )
    category: Mapped[str | None] = mapped_column(String(100))
    requester_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    assignee_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    company: Mapped[Company] = relationship(back_populates="tickets")
    requester: Mapped[Customer] = relationship(back_populates="tickets")
    assignee: Mapped[User | None] = relationship(
        back_populates="assigned_tickets")
    comments: Mapped[list[Comment]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
    )
    events: Mapped[list[TicketEvent]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
    )
    idempotency_keys: Mapped[list[IdempotencyKey]
                             ] = relationship(back_populates="ticket")
