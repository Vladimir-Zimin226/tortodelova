from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction, TransactionType

logger = logging.getLogger(__name__)


class TransactionService:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        amount: int,
        tx_type: TransactionType,
        description: str | None = None,
    ) -> Transaction:
        """
        Создать транзакцию (без изменения баланса).

        Базовая валидация суммы (> 0) выполняется в Transaction.create().
        """
        tx = Transaction.create(
            user_id=user_id,
            amount=amount,
            tx_type=tx_type,
            description=description,
        )
        session.add(tx)
        await session.flush()
        await session.refresh(tx)

        logger.info(
            "TransactionService.create: tx_id=%s user_id=%s type=%s amount=%s",
            tx.id,
            tx.user_id,
            tx.type,
            tx.amount,
        )
        return tx

    async def get(self, session: AsyncSession, tx_id: int) -> Optional[Transaction]:
        tx = await session.get(Transaction, tx_id)
        logger.info(
            "TransactionService.get: tx_id=%s found=%s",
            tx_id,
            bool(tx),
        )
        return tx

    async def list_by_user(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Transaction]:
        res = await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        txs = res.scalars().all()
        logger.info(
            "TransactionService.list_by_user: user_id=%s returned=%s "
            "(offset=%s, limit=%s)",
            user_id,
            len(txs),
            offset,
            limit,
        )
        return txs

    async def list_all(
        self,
        session: AsyncSession,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Transaction]:
        """
        Список всех транзакций (для админки).
        """
        res = await session.execute(
            select(Transaction)
            .order_by(Transaction.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        txs = res.scalars().all()
        logger.info(
            "TransactionService.list_all: returned=%s (offset=%s, limit=%s)",
            len(txs),
            offset,
            limit,
        )
        return txs

    async def delete(self, session: AsyncSession, tx_id: int) -> bool:
        res = await session.execute(
            delete(Transaction).where(Transaction.id == tx_id)
        )
        await session.flush()
        deleted = res.rowcount or 0

        logger.info(
            "TransactionService.delete: tx_id=%s deleted=%s",
            tx_id,
            bool(deleted),
        )
        return bool(deleted)


transaction_service = TransactionService()