from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User
from app.models.transaction import TransactionType
from app.services.repositories.user_service import user_service
from app.services.repositories.transaction_service import transaction_service
from app.api.routes.auth import get_current_user

from app.api.schemas.user import UserProfileOut, BalanceOut, DepositRequest, TransactionOut

router = APIRouter(
    prefix="/api/me",
    tags=["user"],
)


@router.get(
    "/profile",
    response_model=UserProfileOut,
)
async def get_profile(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Профиль текущего пользователя.
    """
    return current_user


@router.get(
    "/balance",
    response_model=BalanceOut,
)
async def get_balance(
    current_user: User = Depends(get_current_user),
) -> BalanceOut:
    """
    Текущий баланс в кредитах.
    """
    return BalanceOut(balance_credits=current_user.balance_credits)


@router.post(
    "/balance/deposit",
    response_model=BalanceOut,
    status_code=status.HTTP_200_OK,
)
async def deposit_balance(
    payload: DepositRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BalanceOut:
    """
    Пополнение баланса текущего пользователя.

    amount > 0, создаётся Transaction типа CREDIT.
    """
    try:
        user, _tx = await user_service.change_balance_with_transaction(
            session,
            user_id=current_user.id,
            amount=payload.amount,
            tx_type=TransactionType.CREDIT,
            description=payload.description or "Balance top-up",
        )
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return BalanceOut(balance_credits=user.balance_credits)


@router.get(
    "/transactions",
    response_model=List[TransactionOut],
)
async def list_my_transactions(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[TransactionOut]:
    """
    История транзакций текущего пользователя.
    """
    txs = await transaction_service.list_by_user(
        session,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return list(txs)
