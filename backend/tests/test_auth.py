from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.dependencies import get_api_key_identity
from app.core.security import RequestIdentity, create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import ApiKey, User


@pytest.fixture
def engine() -> Iterator[Engine]:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    try:
        yield test_engine
    finally:
        Base.metadata.drop_all(test_engine)
        test_engine.dispose()


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def register_user(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Support Company",
            "email": email,
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_register_login_and_me(client: TestClient) -> None:
    registration = register_user(client, "owner@example.com")

    me_response = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {registration['access_token']}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "owner@example.com"
    assert me_response.json()["role"] == "OWNER"

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "owner@example.com",
            "password": "correct horse battery staple",
        },
    )

    assert login_response.status_code == 200
    assert login_response.json()["token_type"] == "bearer"


def test_login_errors_do_not_enumerate_users(client: TestClient) -> None:
    register_user(client, "owner@example.com")
    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "wrong password"},
    )
    unknown_email = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "wrong password"},
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_inactive_user_cannot_login_or_use_existing_token(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = register_user(client, "inactive@example.com")
    user = db_session.scalar(
        select(User).where(User.email == "inactive@example.com")
    )
    assert user is not None
    user.is_active = False
    db_session.commit()

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "inactive@example.com",
            "password": "correct horse battery staple",
        },
    )
    me_response = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {registration['access_token']}"},
    )

    assert login_response.status_code == 401
    assert me_response.status_code == 401


def test_identity_cannot_cross_company_boundary(client: TestClient) -> None:
    company_a = register_user(client, "a@example.com")
    company_b = register_user(client, "b@example.com")
    forged_token = create_access_token(
        RequestIdentity(
            principal_type="user",
            principal_id=UUID(company_a["user"]["id"]),
            company_id=UUID(company_b["user"]["company_id"]),
        )
    )

    response = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {forged_token}"},
    )

    assert response.status_code == 401


def test_api_key_is_hashed_tracked_and_revocable(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = register_user(client, "owner@example.com")
    headers = {"Authorization": f"Bearer {registration['access_token']}"}
    create_response = client.post(
        "/api/v1/auth/api-keys",
        headers=headers,
        json={"name": "Ticket intake"},
    )

    assert create_response.status_code == 201
    api_key_data = create_response.json()
    raw_api_key = api_key_data["api_key"]
    stored_key = db_session.get(ApiKey, UUID(api_key_data["id"]))
    assert stored_key is not None
    assert stored_key.key_hash != raw_api_key

    identity = get_api_key_identity(raw_api_key, db_session)
    assert identity.company_id == UUID(registration["user"]["company_id"])
    db_session.refresh(stored_key)
    assert stored_key.last_used_at is not None

    revoke_response = client.delete(
        f"/api/v1/auth/api-keys/{api_key_data['id']}",
        headers=headers,
    )
    assert revoke_response.status_code == 200

    db_session.expire(stored_key)
    with pytest.raises(HTTPException) as error:
        get_api_key_identity(raw_api_key, db_session)
    assert error.value.status_code == 401
