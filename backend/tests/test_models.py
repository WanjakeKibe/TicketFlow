from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models import (
    ApiKey,
    Comment,
    Company,
    Customer,
    IdempotencyKey,
    Ticket,
    TicketEvent,
    TicketEventType,
    TicketPriority,
    TicketStatus,
    User,
    UserRole,
)
from app.models.common import utc_now


DOMAIN_TABLES = {
    "companies",
    "users",
    "api_keys",
    "customers",
    "tickets",
    "comments",
    "ticket_events",
    "idempotency_keys",
}
TENANT_TABLES = DOMAIN_TABLES - {"companies"}


def test_domain_tables_exist() -> None:
    table_names = set(inspect(get_engine()).get_table_names())

    assert DOMAIN_TABLES <= table_names


def test_tenant_tables_require_company_id() -> None:
    inspector = inspect(get_engine())

    for table_name in TENANT_TABLES:
        columns = {
            column["name"]: column
            for column in inspector.get_columns(table_name)
        }

        assert columns["company_id"]["nullable"] is False


def test_ticket_graph_persists() -> None:
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    try:
        company = Company(name="Example Support")
        user = User(
            company=company,
            email="agent@example.test",
            password_hash="not-a-real-password-hash",
            role=UserRole.AGENT,
        )
        customer = Customer(company=company, name="Example Customer")
        ticket = Ticket(
            company=company,
            requester=customer,
            assignee=user,
            title="Example ticket",
            description="A persistence test ticket.",
            status=TicketStatus.OPEN,
            priority=TicketPriority.NORMAL,
        )
        comment = Comment(
            company=company,
            ticket=ticket,
            author=user,
            body="Test comment",
        )
        event = TicketEvent(
            company=company,
            ticket=ticket,
            actor=user,
            event_type=TicketEventType.CREATED,
            new_value=TicketStatus.OPEN.value,
        )
        api_key = ApiKey(
            company=company,
            key_hash="test-key-hash",
            name="Test intake key",
        )
        idempotency_key = IdempotencyKey(
            company=company,
            key="test-idempotency-key",
            request_hash="a" * 64,
            response_status=201,
            response_body={"ticket_id": str(ticket.id)},
            ticket=ticket,
            expires_at=utc_now() + timedelta(hours=1),
        )
        session.add_all([company, user, customer, ticket,
                        comment, event, api_key, idempotency_key])
        session.flush()

        assert ticket.company_id == company.id
        assert comment.ticket_id == ticket.id
        assert event.ticket_id == ticket.id
        assert idempotency_key.ticket_id == ticket.id
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


def test_user_requires_company() -> None:
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    try:
        session.add(
            User(
                email="orphan@example.test",
                password_hash="not-a-real-password-hash",
                role=UserRole.AGENT,
            )
        )

        with pytest.raises(SQLAlchemyError):
            session.flush()
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


def test_user_email_is_unique_within_company() -> None:
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    try:
        company = Company(name="Unique Email Company")
        session.add(company)
        session.flush()
        session.add_all(
            [
                User(
                    company_id=company.id,
                    email="same@example.test",
                    password_hash="hash-1",
                    role=UserRole.AGENT,
                ),
                User(
                    company_id=company.id,
                    email="same@example.test",
                    password_hash="hash-2",
                    role=UserRole.AGENT,
                ),
            ]
        )

        with pytest.raises(SQLAlchemyError):
            session.flush()
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


def test_ticket_requires_existing_requester() -> None:
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    try:
        company = Company(name="Foreign Key Company")
        session.add(company)
        session.flush()
        session.add(
            Ticket(
                company_id=company.id,
                requester_id=uuid4(),
                title="Invalid requester",
            )
        )

        with pytest.raises(SQLAlchemyError):
            session.flush()
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


def test_idempotency_key_is_unique_within_company() -> None:
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    try:
        company = Company(name="Idempotency Company")
        session.add(company)
        session.flush()
        expires_at = utc_now() + timedelta(hours=1)
        session.add_all(
            [
                IdempotencyKey(
                    company_id=company.id,
                    key="same-key",
                    request_hash="a" * 64,
                    response_status=201,
                    response_body={},
                    expires_at=expires_at,
                ),
                IdempotencyKey(
                    company_id=company.id,
                    key="same-key",
                    request_hash="b" * 64,
                    response_status=201,
                    response_body={},
                    expires_at=expires_at,
                ),
            ]
        )

        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
