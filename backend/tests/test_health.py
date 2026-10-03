import asyncio

import httpx

from app.main import app


async def get_response(
    path: str,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(path, headers=headers)


def test_root_returns_api_identity() -> None:
    response = asyncio.run(get_response("/"))

    assert response.status_code == 200
    assert response.json() == {
        "message": "Welcome to TicketFlow API",
        "version": "0.1.0",
    }


def test_health_returns_healthy_status() -> None:
    response = asyncio.run(get_response("/api/v1/health"))

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_request_id_is_returned() -> None:
    response = asyncio.run(
        get_response("/", headers={"X-Request-ID": "test-request"})
    )

    assert response.headers["X-Request-ID"] == "test-request"


def test_local_frontend_origin_is_allowed() -> None:
    response = asyncio.run(
        get_response("/", headers={"Origin": "http://localhost:5173"})
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
