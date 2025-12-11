from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.api.routes.auth import get_current_user
from app.models.user import User, UserRole
from app.models.transaction import TransactionType, Transaction
from app.services.repositories.user_service import user_service
from app.services.repositories.transaction_service import transaction_service
from app.services.repositories.prediction_service import prediction_service

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
)


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Зависимость, разрешающая доступ только администраторам.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user

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

@router.get("/users", response_model=List[AdminUserOut])
async def admin_list_users(
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[AdminUserOut]:
    """
    Список пользователей для администратора.
    """
    users = await user_service.list(session, limit=limit, offset=offset)
    return list(users)


@router.post("/users/balance", response_model=AdminUserOut)
async def admin_change_user_balance(
    payload: AdminChangeBalanceRequest,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> AdminUserOut:
    """
    Пополнение баланса пользователю от имени администратора.

    amount > 0, создаётся Transaction типа CREDIT.
    """
    from app.models.transaction import TransactionType

    try:
        user, _tx = await user_service.change_balance_with_transaction(
            session,
            user_id=payload.user_id,
            amount=payload.amount,
            tx_type=TransactionType.CREDIT,
            description=payload.description or "Admin balance top-up",
        )
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return user


@router.get("/transactions", response_model=List[AdminTransactionOut])
async def admin_list_transactions(
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[AdminTransactionOut]:
    """
    Список всех транзакций в системе для администратора.
    """
    # Нужен метод list_all в transaction_service.
    txs = await transaction_service.list_all(
        session,
        limit=limit,
        offset=offset,
    )
    return list(txs)


@router.get("/predictions", response_model=List[AdminPredictionOut])
async def admin_list_predictions(
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[AdminPredictionOut]:
    """
    Список всех prediction-запросов в системе для администратора.
    """
    items = await prediction_service.list_all(
        session,
        limit=limit,
        offset=offset,
    )
    return list(items)
