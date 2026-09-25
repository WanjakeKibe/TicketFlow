from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API-first, multi-tenant ticketing for support teams.",
)

app.include_router(health_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "message": "Welcome to TicketFlow API",
        "version": settings.app_version,
    }
