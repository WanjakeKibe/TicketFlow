from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta, timezone
import hashlib
import json
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import RequestIdentity
from app.models import (
    Comment,
    Customer,
    IdempotencyKey,
    Ticket,
    TicketEvent,
    TicketEventType,
    User,
    UserRole,
)
from app.models.common import utc_now
from app.models.enums import TicketPriority, TicketStatus
from app.schemas.tickets import (
    CreateCommentRequest,
    CreateTicketRequest,
    TicketResponse,
    UpdateTicketRequest,
)


class TicketNotFoundError(Exception):
    pass


class TicketForbiddenError(Exception):
    pass


class TicketConflictError(Exception):
    pass


class TicketReferenceNotFoundError(Exception):
    pass


class TicketTransitionError(Exception):
    pass


class IdempotencyConflictError(Exception):
    pass


ALLOWED_STATUS_TRANSITIONS = {
    TicketStatus.OPEN: {TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS},
    TicketStatus.ASSIGNED: {TicketStatus.IN_PROGRESS},
    TicketStatus.IN_PROGRESS: {TicketStatus.RESOLVED},
    TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.OPEN},
    TicketStatus.CLOSED: set(),
}
IDEMPOTENCY_TTL = timedelta(hours=24)


def _add_event(
    db: Session,
    ticket: Ticket,
    actor: RequestIdentity,
    event_type: TicketEventType,
    previous_value: str | None,
    new_value: str | None,
) -> None:
    db.add(
        TicketEvent(
            company_id=ticket.company_id,
            ticket_id=ticket.id,
            actor_id=actor.principal_id if actor.principal_type == "user" else None,
            event_type=event_type,
            previous_value=previous_value,
            new_value=new_value,
        )
    )


def _value(value: object) -> str | None:
    return str(value) if value is not None else None


def _request_hash(request: CreateTicketRequest) -> str:
    payload = request.model_dump(mode="json")
    payload["title"] = payload["title"].strip()
    payload["category"] = payload["category"].strip() if payload["category"] else None
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _stored_response(ticket: Ticket) -> dict:
    return TicketResponse.model_validate(ticket, from_attributes=True).model_dump(
        mode="json"
    )


def _ticket_from_stored_response(
    db: Session,
    company_id: UUID,
    response_body: dict,
) -> Ticket:
    ticket_id = response_body.get("id")
    if not isinstance(ticket_id, str):
        raise TicketNotFoundError("Stored idempotent ticket was not found")
    try:
        return get_ticket(db, company_id, UUID(ticket_id))
    except ValueError:
        raise TicketNotFoundError("Stored idempotent ticket was not found") from None


def _get_idempotency_record(
    db: Session,
    company_id: UUID,
    key: str,
    request_hash: str,
) -> dict | None:
    record = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.company_id == company_id,
            IdempotencyKey.key == key,
        )
    )
    if record is None:
        return None
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= utc_now():
        db.delete(record)
        db.flush()
        return None
    if record.request_hash != request_hash:
        raise IdempotencyConflictError("Idempotency key was used with a different request")
    return record.response_body


def _get_customer(
    db: Session,
    company_id: UUID,
    customer_id: UUID,
) -> Customer:
    customer = db.scalar(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.company_id == company_id,
        )
    )
    if customer is None:
        raise TicketReferenceNotFoundError("Requester was not found")
    return customer


def _get_assignee(
    db: Session,
    company_id: UUID,
    assignee_id: UUID,
) -> User:
    assignee = db.scalar(
        select(User).where(
            User.id == assignee_id,
            User.company_id == company_id,
            User.is_active.is_(True),
        )
    )
    if assignee is None:
        raise TicketReferenceNotFoundError("Assignee was not found")
    return assignee


def _can_manage_ticket(actor: RequestIdentity) -> bool:
    return actor.principal_type == "user" and actor.role in {
        UserRole.OWNER,
        UserRole.MANAGER,
    }


def create_ticket(
    db: Session,
    company_id: UUID,
    request: CreateTicketRequest,
    actor: RequestIdentity,
    idempotency_key: str | None = None,
) -> tuple[Ticket, dict]:
    request_hash = _request_hash(request) if idempotency_key else None
    if idempotency_key and request_hash:
        stored_response = _get_idempotency_record(
            db, company_id, idempotency_key, request_hash
        )
        if stored_response is not None:
            ticket = _ticket_from_stored_response(db, company_id, stored_response)
            return ticket, stored_response
    _get_customer(db, company_id, request.requester_id)
    if request.assignee_id is not None:
        if not _can_manage_ticket(actor):
            raise TicketForbiddenError("Only managers can assign tickets")
        _get_assignee(db, company_id, request.assignee_id)

    ticket = Ticket(
        company_id=company_id,
        title=request.title.strip(),
        description=request.description,
        status=request.status,
        priority=request.priority,
        category=request.category.strip() if request.category else None,
        requester_id=request.requester_id,
        assignee_id=request.assignee_id,
    )
    db.add(ticket)
    db.flush()
    _add_event(
        db,
        ticket,
        actor,
        TicketEventType.CREATED,
        None,
        ticket.status.value,
    )
    response_body = _stored_response(ticket)
    if idempotency_key and request_hash:
        record = IdempotencyKey(
            company_id=company_id,
            key=idempotency_key,
            request_hash=request_hash,
            response_status=201,
            response_body=response_body,
            ticket_id=ticket.id,
            expires_at=utc_now() + IDEMPOTENCY_TTL,
        )
        try:
            with db.begin_nested():
                db.add(record)
                db.flush()
        except IntegrityError:
            db.rollback()
            existing = _get_idempotency_record(
                db, company_id, idempotency_key, request_hash
            )
            if existing is None:
                raise
            return _ticket_from_stored_response(db, company_id, existing), existing
    db.commit()
    db.refresh(ticket)
    return ticket, response_body


def get_ticket(
    db: Session,
    company_id: UUID,
    ticket_id: UUID,
) -> Ticket:
    ticket = db.scalar(
        select(Ticket).where(
            Ticket.id == ticket_id,
            Ticket.company_id == company_id,
        )
    )
    if ticket is None:
        raise TicketNotFoundError("Ticket was not found")
    return ticket


def list_tickets(
    db: Session,
    company_id: UUID,
    *,
    page: int,
    page_size: int,
    status: TicketStatus | None = None,
    priority: TicketPriority | None = None,
    assignee_id: UUID | None = None,
    search: str | None = None,
) -> tuple[Sequence[Ticket], int]:
    conditions = [Ticket.company_id == company_id]
    if status is not None:
        conditions.append(Ticket.status == status)
    if priority is not None:
        conditions.append(Ticket.priority == priority)
    if assignee_id is not None:
        conditions.append(Ticket.assignee_id == assignee_id)
    if search:
        search_pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Ticket.title.ilike(search_pattern),
                Ticket.description.ilike(search_pattern),
                Ticket.category.ilike(search_pattern),
            )
        )

    total = db.scalar(
        select(func.count()).select_from(Ticket).where(*conditions)
    ) or 0
    tickets = db.scalars(
        select(Ticket)
        .where(*conditions)
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return tickets, total


def update_ticket(
    db: Session,
    company_id: UUID,
    ticket_id: UUID,
    request: UpdateTicketRequest,
    actor: RequestIdentity,
) -> Ticket:
    ticket = db.scalar(
        select(Ticket)
        .where(
            Ticket.id == ticket_id,
            Ticket.company_id == company_id,
        )
        .with_for_update()
    )
    if ticket is None:
        raise TicketNotFoundError("Ticket was not found")
    if ticket.version != request.expected_version:
        raise TicketConflictError("Ticket version is stale")
    if not _can_manage_ticket(actor) and (
        actor.principal_type != "user"
        or ticket.assignee_id != actor.principal_id
    ):
        raise TicketForbiddenError("You cannot update this ticket")

    fields = request.model_fields_set
    if not _can_manage_ticket(actor) and fields.intersection(
        {"priority", "category", "assignee_id", "requester_id"}
    ):
        raise TicketForbiddenError("Only managers can change ticket ownership")
    if "requester_id" in fields and request.requester_id is not None:
        _get_customer(db, company_id, request.requester_id)
    if "assignee_id" in fields and request.assignee_id is not None:
        _get_assignee(db, company_id, request.assignee_id)
    if "status" in fields and request.status is not None:
        if request.status != ticket.status and request.status not in ALLOWED_STATUS_TRANSITIONS[ticket.status]:
            raise TicketTransitionError(
                f"Cannot transition ticket from {ticket.status.value} to {request.status.value}"
            )
        if request.status != ticket.status:
            _add_event(
                db,
                ticket,
                actor,
                TicketEventType.STATUS_CHANGED,
                ticket.status.value,
                request.status.value,
            )
    if "assignee_id" in fields and request.assignee_id != ticket.assignee_id:
        _add_event(
            db,
            ticket,
            actor,
            TicketEventType.ASSIGNMENT_CHANGED,
            _value(ticket.assignee_id),
            _value(request.assignee_id),
        )
    if "priority" in fields and request.priority is not None and request.priority != ticket.priority:
        _add_event(
            db,
            ticket,
            actor,
            TicketEventType.PRIORITY_CHANGED,
            ticket.priority.value,
            request.priority.value,
        )
    if "category" in fields:
        new_category = request.category.strip() if request.category else None
        if new_category != ticket.category:
            _add_event(
                db,
                ticket,
                actor,
                TicketEventType.CATEGORY_CHANGED,
                ticket.category,
                new_category,
            )
    if "title" in fields:
        ticket.title = request.title.strip() if request.title else ticket.title
    if "description" in fields:
        ticket.description = request.description
    if "status" in fields:
        ticket.status = request.status or ticket.status
    if "priority" in fields:
        ticket.priority = request.priority or ticket.priority
    if "category" in fields:
        ticket.category = request.category.strip() if request.category else None
    if "requester_id" in fields:
        ticket.requester_id = request.requester_id or ticket.requester_id
    if "assignee_id" in fields:
        ticket.assignee_id = request.assignee_id
    ticket.version += 1
    db.commit()
    db.refresh(ticket)
    return ticket


def add_comment(
    db: Session,
    company_id: UUID,
    ticket_id: UUID,
    request: CreateCommentRequest,
    actor: RequestIdentity,
) -> Comment:
    if actor.principal_type != "user":
        raise TicketForbiddenError("Only users can add comments")
    ticket = db.scalar(
        select(Ticket)
        .where(Ticket.id == ticket_id, Ticket.company_id == company_id)
        .with_for_update()
    )
    if ticket is None:
        raise TicketNotFoundError("Ticket was not found")
    if ticket.version != request.expected_version:
        raise TicketConflictError("Ticket version is stale")
    comment = Comment(
        company_id=company_id,
        ticket_id=ticket.id,
        author_id=actor.principal_id,
        body=request.body.strip(),
        is_internal=request.is_internal,
    )
    db.add(comment)
    db.flush()
    _add_event(
        db,
        ticket,
        actor,
        TicketEventType.COMMENT_ADDED,
        None,
        comment.id.hex,
    )
    ticket.version += 1
    db.commit()
    db.refresh(comment)
    return comment


def list_ticket_events(
    db: Session,
    company_id: UUID,
    ticket_id: UUID,
) -> Sequence[TicketEvent]:
    ticket = db.scalar(
        select(Ticket.id).where(
            Ticket.id == ticket_id,
            Ticket.company_id == company_id,
        )
    )
    if ticket is None:
        raise TicketNotFoundError("Ticket was not found")
    return db.scalars(
        select(TicketEvent)
        .where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.company_id == company_id,
        )
        .order_by(TicketEvent.occurred_at.asc(), TicketEvent.id.asc())
    ).all()
