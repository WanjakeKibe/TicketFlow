from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import CreatedAtMixin, UUIDPrimaryKeyMixin, utc_now
from app.models.enums import TicketEventType

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.ticket import Ticket
    from app.models.user import User


class TicketEvent(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "ticket_events"

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    ticket_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    event_type: Mapped[TicketEventType] = mapped_column(
        Enum(TicketEventType, name="ticket_event_type"), nullable=False
    )
    previous_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    company: Mapped[Company] = relationship(back_populates="ticket_events")
    ticket: Mapped[Ticket] = relationship(back_populates="events")
    actor: Mapped[User | None] = relationship(back_populates="ticket_events")
