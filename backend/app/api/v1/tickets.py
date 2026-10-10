from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.v1.dependencies import AuthenticatedIdentity
from app.db.session import get_db
from app.models.enums import TicketPriority, TicketStatus
from app.schemas.tickets import (
    CommentResponse,
    CreateCommentRequest,
    CreateTicketRequest,
    TicketListResponse,
    TicketEventResponse,
    TicketResponse,
    UpdateTicketRequest,
)
from app.services.tickets import (
    TicketConflictError,
    TicketForbiddenError,
    IdempotencyConflictError,
    TicketNotFoundError,
    TicketReferenceNotFoundError,
    TicketTransitionError,
    add_comment,
    create_ticket,
    get_ticket,
    list_ticket_events,
    list_tickets,
    update_ticket,
)


router = APIRouter(prefix="/tickets", tags=["tickets"])


def _ticket_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Ticket was not found",
    )


def _to_response(ticket) -> TicketResponse:
    return TicketResponse.model_validate(ticket, from_attributes=True)


def _to_comment_response(comment) -> CommentResponse:
    return CommentResponse.model_validate(comment, from_attributes=True)


def _to_event_response(event) -> TicketEventResponse:
    return TicketEventResponse.model_validate(event, from_attributes=True)


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create(
    request: CreateTicketRequest,
    identity: AuthenticatedIdentity,
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=255),
    ] = None,
) -> TicketResponse | JSONResponse:
    try:
        ticket, response_body = create_ticket(
            db, identity.company_id, request, identity, idempotency_key
        )
    except TicketForbiddenError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from None
    except TicketReferenceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from None
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from None
    if idempotency_key:
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=response_body)
    return _to_response(ticket)


@router.get("", response_model=TicketListResponse)
def list_all(
    identity: AuthenticatedIdentity,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[
        TicketStatus | None,
        Query(alias="status"),
    ] = None,
    priority: TicketPriority | None = None,
    assignee_id: UUID | None = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
) -> TicketListResponse:
    tickets, total = list_tickets(
        db,
        identity.company_id,
        page=page,
        page_size=page_size,
        status=status_filter,
        priority=priority,
        assignee_id=assignee_id,
        search=search,
    )
    return TicketListResponse(
        items=[_to_response(ticket) for ticket in tickets],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_one(
    ticket_id: UUID,
    identity: AuthenticatedIdentity,
    db: Annotated[Session, Depends(get_db)],
) -> TicketResponse:
    try:
        return _to_response(get_ticket(db, identity.company_id, ticket_id))
    except TicketNotFoundError:
        raise _ticket_not_found() from None


@router.patch("/{ticket_id}", response_model=TicketResponse)
def update(
    ticket_id: UUID,
    request: UpdateTicketRequest,
    identity: AuthenticatedIdentity,
    db: Annotated[Session, Depends(get_db)],
) -> TicketResponse:
    try:
        ticket = update_ticket(
            db,
            identity.company_id,
            ticket_id,
            request,
            identity,
        )
    except TicketNotFoundError:
        raise _ticket_not_found() from None
    except TicketForbiddenError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from None
    except TicketReferenceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from None
    except TicketConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from None
    except TicketTransitionError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from None
    return _to_response(ticket)


@router.post(
    "/{ticket_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def comment(
    ticket_id: UUID,
    request: CreateCommentRequest,
    identity: AuthenticatedIdentity,
    db: Annotated[Session, Depends(get_db)],
) -> CommentResponse:
    try:
        return _to_comment_response(
            add_comment(db, identity.company_id, ticket_id, request, identity)
        )
    except TicketNotFoundError:
        raise _ticket_not_found() from None
    except TicketForbiddenError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from None
    except TicketConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from None


@router.get(
    "/{ticket_id}/events",
    response_model=list[TicketEventResponse],
)
def events(
    ticket_id: UUID,
    identity: AuthenticatedIdentity,
    db: Annotated[Session, Depends(get_db)],
) -> list[TicketEventResponse]:
    try:
        return [
            _to_event_response(event)
            for event in list_ticket_events(db, identity.company_id, ticket_id)
        ]
    except TicketNotFoundError:
        raise _ticket_not_found() from None
