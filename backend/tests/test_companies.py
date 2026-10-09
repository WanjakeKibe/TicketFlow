from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User, UserRole
from app.services.auth import issue_user_access_token


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_user_access_token(user)}"}


def create_company_user(
    db_session: Session,
    company_id: UUID,
    email: str,
    role: UserRole,
) -> User:
    user = User(
        company_id=company_id,
        email=email,
        password_hash=hash_password("correct horse battery staple"),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_company(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/companies",
        json={
            "company_name": "Support Company",
            "email": email,
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_get_company(client: TestClient) -> None:
    registration = create_company(client, "owner@example.com")
    company_id = registration["user"]["company_id"]

    response = client.get(
        f"/api/v1/companies/{company_id}",
        headers={"Authorization": f"Bearer {registration['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == company_id
    assert response.json()["name"] == "Support Company"


def test_company_resources_are_not_visible_across_tenants(
    client: TestClient,
    db_session: Session,
) -> None:
    company_a = create_company(client, "a@example.com")
    company_b = create_company(client, "b@example.com")
    company_b_owner = db_session.get(
        User,
        UUID(company_b["user"]["id"]),
    )
    assert company_b_owner is not None
    company_b_agent = create_company_user(
        db_session,
        company_b_owner.company_id,
        "b-agent@example.com",
        UserRole.AGENT,
    )

    response = client.get(
        f"/api/v1/companies/{company_a['user']['company_id']}/users",
        headers=auth_headers(company_b_agent),
    )

    assert response.status_code == 404


def test_owner_and_manager_can_list_users_but_agents_cannot(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = create_company(client, "owner@example.com")
    owner = db_session.get(User, UUID(registration["user"]["id"]))
    assert owner is not None
    manager = create_company_user(
        db_session,
        owner.company_id,
        "manager@example.com",
        UserRole.MANAGER,
    )
    agent = create_company_user(
        db_session,
        owner.company_id,
        "agent@example.com",
        UserRole.AGENT,
    )
    endpoint = f"/api/v1/companies/{owner.company_id}/users"

    owner_response = client.get(endpoint, headers=auth_headers(owner))
    manager_response = client.get(endpoint, headers=auth_headers(manager))
    agent_response = client.get(endpoint, headers=auth_headers(agent))

    assert owner_response.status_code == 200
    assert manager_response.status_code == 200
    assert agent_response.status_code == 403
    assert owner_response.json()["total"] == 3
    assert {user["role"] for user in manager_response.json()["items"]} == {
        "OWNER",
        "MANAGER",
        "AGENT",
    }


def test_manager_cannot_use_owner_only_api_key_operations(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = create_company(client, "owner@example.com")
    owner = db_session.get(User, UUID(registration["user"]["id"]))
    assert owner is not None
    manager = create_company_user(
        db_session,
        owner.company_id,
        "manager@example.com",
        UserRole.MANAGER,
    )

    response = client.post(
        "/api/v1/auth/api-keys",
        headers=auth_headers(manager),
        json={"name": "Manager key"},
    )

    assert response.status_code == 403
