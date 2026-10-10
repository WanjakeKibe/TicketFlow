from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import TicketPriority, TicketStatus


class CreateTicketRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: TicketStatus = TicketStatus.OPEN
    priority: TicketPriority = TicketPriority.NORMAL
    category: str | None = Field(default=None, max_length=100)
    requester_id: UUID
    assignee_id: UUID | None = None


class UpdateTicketRequest(BaseModel):
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    category: str | None = Field(default=None, max_length=100)
    requester_id: UUID | None = None
    assignee_id: UUID | None = None


class CreateCommentRequest(BaseModel):
    expected_version: int = Field(ge=1)
    body: str = Field(min_length=1)
    is_internal: bool = False


class CommentResponse(BaseModel):
    id: UUID
    company_id: UUID
    ticket_id: UUID
    author_id: UUID
    body: str
    is_internal: bool
    created_at: datetime


class TicketEventResponse(BaseModel):
    id: UUID
    company_id: UUID
    ticket_id: UUID
    actor_id: UUID | None
    event_type: str
    previous_value: str | None
    new_value: str | None
    occurred_at: datetime
    created_at: datetime


class TicketResponse(BaseModel):
    id: UUID
    public_id: UUID
    company_id: UUID
    title: str
    description: str | None
    status: TicketStatus
    priority: TicketPriority
    category: str | None
    requester_id: UUID
    assignee_id: UUID | None
    created_at: datetime
    updated_at: datetime
    version: int


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
