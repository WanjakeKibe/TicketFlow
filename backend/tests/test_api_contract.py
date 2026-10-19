from fastapi.testclient import TestClient


def test_api_errors_use_the_shared_contract(client: TestClient) -> None:
    unauthenticated = client.get("/api/v1/tickets")
    invalid_credentials = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "not-a-match"},
    )
    invalid_request = client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "x"},
    )
    missing_route = client.get("/api/v1/no-such-resource")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json() == {
        "error": {
            "code": "AUTHENTICATION_FAILED",
            "message": "Invalid authentication credentials",
        }
    }
    assert invalid_credentials.json() == unauthenticated.json()
    assert invalid_request.status_code == 422
    assert invalid_request.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
        }
    }
    assert missing_route.status_code == 404
    assert missing_route.json() == {
        "error": {"code": "RESOURCE_NOT_FOUND", "message": "Resource was not found"}
    }


def test_openapi_documents_errors_auth_pagination_and_examples(
    client: TestClient,
) -> None:
    openapi = client.get("/openapi.json").json()
    paths = openapi["paths"]
    create_ticket = paths["/api/v1/tickets"]["post"]
    list_tickets = paths["/api/v1/tickets"]["get"]
    query_parameters = {
        parameter["name"]: parameter
        for parameter in list_tickets["parameters"]
        if parameter["in"] == "query"
    }

    assert "requestBody" in create_ticket
    assert create_ticket["responses"]["201"]["content"]["application/json"]["schema"]
    for status_code in ("401", "409", "422"):
        error_content = create_ticket["responses"][status_code]["content"][
            "application/json"
        ]
        response_schema = error_content["schema"]
        assert response_schema["$ref"].endswith("ApiErrorResponse")
        assert error_content["examples"]
    assert "Idempotency-Key" in {
        parameter["name"] for parameter in create_ticket["parameters"]
    }
    assert {"page", "page_size", "status", "priority", "assignee_id", "search"} <= set(
        query_parameters
    )
    assert query_parameters["page"]["description"]
    assert query_parameters["page_size"]["description"]
    assert list_tickets["security"]
    assert openapi["components"]["securitySchemes"]
    assert openapi["components"]["schemas"]["CreateTicketRequest"]["examples"]