from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Customer, User, UserRole
from app.services.auth import issue_user_access_token


PASSWORD = "correct horse battery staple"


def bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_user_access_token(user)}"}


def register_owner(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "company_name": f"{email} Support",
            "email": email,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    return response.json()


def add_customer(db_session: Session, company_id: UUID) -> Customer:
    customer = Customer(
        company_id=company_id,
        name="Example Customer",
        email="customer@example.com",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


def add_user(
    db_session: Session,
    company_id: UUID,
    email: str,
    role: UserRole,
) -> User:
    user = User(
        company_id=company_id,
        email=email,
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def ticket_payload(customer_id: UUID, **overrides) -> dict:
    payload = {
        "title": "Cannot sign in",
        "description": "The customer cannot access the portal.",
        "category": "Access",
        "requester_id": str(customer_id),
    }
    payload.update(overrides)
    return payload


def test_user_can_create_get_and_list_company_tickets(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = register_owner(client, "owner@example.com")
    owner = db_session.scalar(
        select(User).where(User.email == "owner@example.com")
    )
    assert owner is not None
    customer = add_customer(db_session, owner.company_id)
    headers = {"Authorization": f"Bearer {registration['access_token']}"}

    create_response = client.post(
        "/api/v1/tickets",
        headers=headers,
        json=ticket_payload(customer.id),
    )
    assert create_response.status_code == 201
    ticket = create_response.json()
    assert ticket["version"] == 1
    assert ticket["requester_id"] == str(customer.id)

    get_response = client.get(
        f"/api/v1/tickets/{ticket['id']}",
        headers=headers,
    )
    list_response = client.get(
        "/api/v1/tickets",
        headers=headers,
        params={"search": "sign in", "page": 1, "page_size": 20},
    )

    assert get_response.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["id"] == ticket["id"]


def test_ticket_list_supports_filters_pagination_and_deterministic_order(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = register_owner(client, "owner@example.com")
    owner = db_session.scalar(
        select(User).where(User.email == "owner@example.com")
    )
    assert owner is not None
    customer = add_customer(db_session, owner.company_id)
    headers = {"Authorization": f"Bearer {registration['access_token']}"}

    for title, priority in [
        ("Urgent outage", "URGENT"),
        ("Normal request", "NORMAL"),
        ("Another urgent", "URGENT"),
    ]:
        response = client.post(
            "/api/v1/tickets",
            headers=headers,
            json=ticket_payload(
                customer.id,
                title=title,
                priority=priority,
            ),
        )
        assert response.status_code == 201

    response = client.get(
        "/api/v1/tickets",
        headers=headers,
        params={"priority": "URGENT", "page": 1, "page_size": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["items"][0]["title"] == "Another urgent"


def test_api_key_can_create_tickets_and_revocation_blocks_creation(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = register_owner(client, "owner@example.com")
    owner = db_session.scalar(
        select(User).where(User.email == "owner@example.com")
    )
    assert owner is not None
    customer = add_customer(db_session, owner.company_id)
    owner_headers = {"Authorization": f"Bearer {registration['access_token']}"}
    key_response = client.post(
        "/api/v1/auth/api-keys",
        headers=owner_headers,
        json={"name": "Ticket intake"},
    )
    raw_key = key_response.json()["api_key"]

    create_response = client.post(
        "/api/v1/tickets",
        headers={"X-API-Key": raw_key},
        json=ticket_payload(customer.id),
    )
    assert create_response.status_code == 201

    revoke_response = client.delete(
        f"/api/v1/auth/api-keys/{key_response.json()['id']}",
        headers=owner_headers,
    )
    assert revoke_response.status_code == 200
    blocked_response = client.post(
        "/api/v1/tickets",
        headers={"X-API-Key": raw_key},
        json=ticket_payload(customer.id, title="Blocked"),
    )
    assert blocked_response.status_code == 401


def test_ticket_updates_enforce_roles_and_expected_version(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = register_owner(client, "owner@example.com")
    owner = db_session.scalar(
        select(User).where(User.email == "owner@example.com")
    )
    assert owner is not None
    customer = add_customer(db_session, owner.company_id)
    agent = add_user(
        db_session,
        owner.company_id,
        "agent@example.com",
        UserRole.AGENT,
    )
    manager = add_user(
        db_session,
        owner.company_id,
        "manager@example.com",
        UserRole.MANAGER,
    )
    owner_headers = bearer(owner)
    ticket_response = client.post(
        "/api/v1/tickets",
        headers=owner_headers,
        json=ticket_payload(customer.id, assignee_id=str(agent.id)),
    )
    assert ticket_response.status_code == 201
    ticket = ticket_response.json()

    agent_update = client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        headers=bearer(agent),
        json={"expected_version": 1, "title": "Agent updated"},
    )
    agent_restricted = client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        headers=bearer(agent),
        json={"expected_version": 2, "priority": "HIGH"},
    )
    manager_update = client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        headers=bearer(manager),
        json={"expected_version": 2, "priority": "HIGH"},
    )
    stale_update = client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        headers=owner_headers,
        json={"expected_version": 2, "title": "Stale"},
    )

    assert agent_update.status_code == 200
    assert agent_update.json()["version"] == 2
    assert agent_restricted.status_code == 403
    assert manager_update.status_code == 200
    assert manager_update.json()["version"] == 3
    assert stale_update.status_code == 409


def test_cross_company_ticket_ids_return_not_found(
    client: TestClient,
    db_session: Session,
) -> None:
    first = register_owner(client, "first@example.com")
    second = register_owner(client, "second@example.com")
    first_owner = db_session.scalar(
        select(User).where(User.email == "first@example.com")
    )
    assert first_owner is not None
    customer = add_customer(db_session, first_owner.company_id)
    ticket_response = client.post(
        "/api/v1/tickets",
        headers={"Authorization": f"Bearer {first['access_token']}"},
        json=ticket_payload(customer.id),
    )
    ticket_id = ticket_response.json()["id"]

    response = client.get(
        f"/api/v1/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )

    assert response.status_code == 404


def test_ticket_lifecycle_comments_and_events(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = register_owner(client, "lifecycle@example.com")
    owner = db_session.scalar(
        select(User).where(User.email == "lifecycle@example.com")
    )
    assert owner is not None
    customer = add_customer(db_session, owner.company_id)
    headers = bearer(owner)
    ticket = client.post(
        "/api/v1/tickets",
        headers=headers,
        json=ticket_payload(customer.id),
    ).json()

    assigned = client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        headers=headers,
        json={"expected_version": 1, "status": "RESOLVED"},
    )
    assert assigned.status_code == 400

    in_progress = client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        headers=headers,
        json={"expected_version": 1, "status": "IN_PROGRESS"},
    )
    assert in_progress.status_code == 200
    assert in_progress.json()["version"] == 2

    comment = client.post(
        f"/api/v1/tickets/{ticket['id']}/comments",
        headers=headers,
        json={
            "expected_version": 2,
            "body": "Investigating the issue.",
            "is_internal": True,
        },
    )
    assert comment.status_code == 201
    assert comment.json()["body"] == "Investigating the issue."

    events = client.get(
        f"/api/v1/tickets/{ticket['id']}/events",
        headers=headers,
    )
    assert events.status_code == 200
    assert [event["event_type"] for event in events.json()] == [
        "CREATED",
        "STATUS_CHANGED",
        "COMMENT_ADDED",
    ]
    assert events.json()[1]["previous_value"] == "OPEN"
    assert events.json()[1]["new_value"] == "IN_PROGRESS"


def test_comment_requires_current_ticket_version(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = register_owner(client, "comment-conflict@example.com")
    owner = db_session.scalar(
        select(User).where(User.email == "comment-conflict@example.com")
    )
    assert owner is not None
    customer = add_customer(db_session, owner.company_id)
    headers = bearer(owner)
    ticket = client.post(
        "/api/v1/tickets",
        headers=headers,
        json=ticket_payload(customer.id),
    ).json()

    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/comments",
        headers=headers,
        json={"expected_version": 99, "body": "Stale comment"},
    )

    assert response.status_code == 409
