from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, conint, ConfigDict

from app.models.user import UserRole
from app.models.transaction import TransactionType


class UserProfileOut(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    balance_credits: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BalanceOut(BaseModel):
    balance_credits: int


class DepositRequest(BaseModel):
    amount: conint(gt=0)
    description: Optional[str] = "Balance top-up"


class TransactionOut(BaseModel):
    id: int
    amount: int
    type: TransactionType
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
