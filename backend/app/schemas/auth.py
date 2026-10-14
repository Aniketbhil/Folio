"""Pydantic schemas for authentication and authorization."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    """Payload for student registration."""

    name: str = Field(..., description="Student full name (1 to 80 characters)")
    email: EmailStr = Field(..., description="Student email address")
    password: str = Field(..., description="Plaintext password to validate and hash")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not (1 <= len(trimmed) <= 80):
            raise ValueError("Name must be between 1 and 80 characters")
        return trimmed

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return str(v).strip().lower()


class LoginRequest(BaseModel):
    """Payload for student login."""

    email: EmailStr = Field(..., description="Student email address")
    password: str = Field(..., description="Plaintext password")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return str(v).strip().lower()


class AuthStudent(BaseModel):
    """Public authenticated student representation without password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: Optional[str] = None


class AuthResponse(BaseModel):
    """Response returned upon successful signup or login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    student: AuthStudent


class ChangePasswordRequest(BaseModel):
    """Payload for password change."""

    current_password: str = Field(..., description="Existing plaintext password")
    new_password: str = Field(..., description="New replacement password")


class ChangePasswordResponse(BaseModel):
    """Response returned upon successful password update."""

    changed: bool = True
