from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.auth import RegisterRequest, UserResponse


class CreateCompanyRequest(RegisterRequest):
    pass


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime


class CompanyUsersResponse(BaseModel):
    items: list[UserResponse]
    total: int = Field(ge=0)
