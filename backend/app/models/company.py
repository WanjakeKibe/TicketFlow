from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.api_key import ApiKey
    from app.models.comment import Comment
    from app.models.customer import Customer
    from app.models.idempotency_key import IdempotencyKey
    from app.models.ticket import Ticket
    from app.models.ticket_event import TicketEvent
    from app.models.user import User


class Company(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    users: Mapped[list[User]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list[ApiKey]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    customers: Mapped[list[Customer]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    tickets: Mapped[list[Ticket]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list[Comment]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    ticket_events: Mapped[list[TicketEvent]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    idempotency_keys: Mapped[list[IdempotencyKey]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
