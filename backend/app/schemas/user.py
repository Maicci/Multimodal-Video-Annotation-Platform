"""User request and response schemas."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.text import DatabaseText


class Role(str, Enum):
    ANNOTATOR = "annotator"
    REVIEWER = "reviewer"
    ADMINISTRATOR = "administrator"

class UserStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"


class RegisterRequest(BaseModel):
    email: DatabaseText = Field(min_length=3, max_length=254)
    full_name: DatabaseText = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.isprintable() or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Enter a valid email address")
        return normalized

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value or not value.isprintable():
            raise ValueError("Enter a name without control characters")
        return value


class UserApprovalRequest(BaseModel):
    role: Role
    

class LoginRequest(BaseModel):
    email: DatabaseText = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserCreate(RegisterRequest):
    role: Role


class RoleUpdate(BaseModel):
    role: Role


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    role: Role | None
    status: UserStatus
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(UserResponse):
    pass
