from __future__ import annotations

from pydantic import BaseModel, EmailStr, constr, ConfigDict

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    # оставляю как было (даже если не используется в роуте)
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    balance_credits: int

    model_config = ConfigDict(from_attributes=True)
