from fastapi import APIRouter, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.api_errors import api_error, documented_errors
from app.db.session import get_engine


router = APIRouter(tags=["health"], responses=documented_errors(500, 503))


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/health/db")
def database_health_check() -> dict[str, str]:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except (ImportError, OSError, SQLAlchemyError) as exc:
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "SERVICE_UNAVAILABLE",
            "Database is unavailable",
        ) from exc

    return {"status": "healthy", "database": "connected"}
