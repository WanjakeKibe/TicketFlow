from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("API key name cannot be blank")
        return normalized


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    api_key: str
    created_at: datetime


class ApiKeyRevocationResponse(BaseModel):
    id: UUID
    revoked_at: datetime
