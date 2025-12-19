from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict

from app.models.user import UserRole
from app.models.transaction import TransactionType


class AdminUserOut(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    balance_credits: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminTransactionOut(BaseModel):
    id: int
    user_id: int
    amount: int
    type: TransactionType
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminPredictionOut(BaseModel):
    id: int
    user_id: int
    prompt_ru: str
    prompt_en: Optional[str] = None
    s3_key: str
    public_url: str
    credits_spent: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminChangeBalanceRequest(BaseModel):
    user_id: int
    amount: int
    description: Optional[str] = "Admin balance change"


class AdminDeleteUserResponse(BaseModel):
    deleted_user_id: int
    message: str = "User deleted"

    model_config = ConfigDict(from_attributes=True)