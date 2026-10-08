from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    api_key: str
    created_at: datetime


class ApiKeyRevocationResponse(BaseModel):
    id: UUID
    revoked_at: datetime
