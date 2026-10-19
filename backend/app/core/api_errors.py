import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.errors import ApiErrorDetail, ApiErrorResponse


logger = logging.getLogger(__name__)


class ApiError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(status_code, detail=message, headers=dict(headers or {}))
        self.code = code


def api_error(
    status_code: int,
    code: str,
    message: str,
    headers: Mapping[str, str] | None = None,
) -> ApiError:
    return ApiError(status_code, code, message, headers)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ApiErrorResponse(
        error=ApiErrorDetail(code=code, message=message)
    ).model_dump(mode="json")
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def _default_http_error(status_code: int) -> tuple[str, str]:
    defaults = {
        400: ("BAD_REQUEST", "The request could not be processed"),
        401: ("AUTHENTICATION_FAILED", "Invalid authentication credentials"),
        403: ("AUTHORIZATION_FAILED", "Insufficient permissions"),
        404: ("RESOURCE_NOT_FOUND", "Resource was not found"),
        405: ("METHOD_NOT_ALLOWED", "Method is not allowed"),
        409: ("RESOURCE_CONFLICT", "The request conflicts with current state"),
        422: ("VALIDATION_ERROR", "Request validation failed"),
        429: ("RATE_LIMITED", "Too many requests"),
        500: ("INTERNAL_SERVER_ERROR", "An unexpected error occurred"),
        503: ("SERVICE_UNAVAILABLE", "The service is unavailable"),
    }
    return defaults.get(
        status_code,
        ("HTTP_ERROR", "The request could not be completed"),
    )


async def handle_http_exception(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    if isinstance(exc, ApiError):
        code, message = exc.code, str(exc.detail)
    else:
        code, message = _default_http_error(exc.status_code)
    return _error_response(exc.status_code, code, message, exc.headers)


async def handle_validation_exception(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return _error_response(422, "VALIDATION_ERROR", "Request validation failed")


async def handle_unexpected_exception(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error(
        "Unhandled API exception",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return _error_response(
        500,
        "INTERNAL_SERVER_ERROR",
        "An unexpected error occurred",
    )


def _documented_error(
    description: str,
    examples: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "model": ApiErrorResponse,
        "description": description,
        "content": {"application/json": {"examples": dict(examples)}},
    }


def _example(code: str, message: str) -> dict[str, Any]:
    return {"value": {"error": {"code": code, "message": message}}}


ERROR_RESPONSES: dict[int, dict[str, Any]] = {
    400: _documented_error(
        "Invalid request or ticket lifecycle transition.",
        {"invalidTransition": _example(
            "INVALID_TICKET_TRANSITION", "Ticket cannot move to the requested status"
        )},
    ),
    401: _documented_error(
        "Authentication failed. Revoked API keys have a distinct error code.",
        {
            "invalidCredentials": _example(
                "AUTHENTICATION_FAILED", "Invalid authentication credentials"
            ),
            "revokedApiKey": _example("API_KEY_REVOKED", "API key has been revoked"),
        },
    ),
    403: _documented_error(
        "The authenticated identity lacks permission.",
        {"forbidden": _example("AUTHORIZATION_FAILED", "Insufficient permissions")},
    ),
    404: _documented_error(
        "The requested resource was not found.",
        {"notFound": _example("RESOURCE_NOT_FOUND", "Resource was not found")},
    ),
    409: _documented_error(
        "Conflict codes include STALE_VERSION, IDEMPOTENCY_CONFLICT, "
        "and RESOURCE_CONFLICT.",
        {
            "staleVersion": _example(
                "STALE_VERSION", "Ticket was updated by another request"
            ),
            "idempotencyConflict": _example(
                "IDEMPOTENCY_CONFLICT",
                "Idempotency key was used with a different request",
            ),
            "resourceConflict": _example(
                "RESOURCE_CONFLICT", "Unable to create company"
            ),
        },
    ),
    422: _documented_error(
        "Request validation failed.",
        {"validation": _example("VALIDATION_ERROR", "Request validation failed")},
    ),
    500: _documented_error(
        "An unexpected server error occurred.",
        {"internalError": _example(
            "INTERNAL_SERVER_ERROR", "An unexpected error occurred"
        )},
    ),
    503: _documented_error(
        "A required service is unavailable.",
        {"serviceUnavailable": _example(
            "SERVICE_UNAVAILABLE", "The service is unavailable"
        )},
    ),
}


def documented_errors(*status_codes: int) -> dict[int, dict[str, Any]]:
    return {code: ERROR_RESPONSES[code] for code in status_codes}


def register_api_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_exception)
    app.add_exception_handler(Exception, handle_unexpected_exception)