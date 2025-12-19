from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.api.routes.auth import get_current_user
from app.models.user import User, UserRole
from app.services.repositories.user_service import user_service
from app.services.repositories.transaction_service import transaction_service
from app.services.repositories.prediction_service import prediction_service

from app.api.schemas.admin import (
    AdminUserOut,
    AdminTransactionOut,
    AdminPredictionOut,
    AdminChangeBalanceRequest,
    AdminDeleteUserResponse,
)

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


@router.delete("/users/{user_id}", response_model=AdminDeleteUserResponse)
async def admin_delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> AdminDeleteUserResponse:
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin can't delete themselves",
        )

    user = await user_service.get(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await user_service.delete(session, user_id)

    return AdminDeleteUserResponse(deleted_user_id=user_id, message="User deleted")

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
