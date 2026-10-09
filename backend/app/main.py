from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import me_router, router as auth_router
from app.api.v1.companies import router as companies_router
from app.api.v1.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware


settings = get_settings()
configure_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API-first, multi-tenant ticketing for support teams.",
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip()
                   for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(me_router, prefix="/api/v1")
app.include_router(companies_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "message": "Welcome to TicketFlow API",
        "version": settings.app_version,
    }
