from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.transaction import Transaction, TransactionType

logger = logging.getLogger(__name__)


class UserService:
    async def create(
        self,
        session: AsyncSession,
        *,
        email: str,
        hashed_password: str,
        role: UserRole = UserRole.USER,
        balance_credits: int = 0,
    ) -> User:
        """
        Создать пользователя.

        Валидация базовых инвариантов (email, хеш пароля, стартовый баланс)
        выполняется на уровне модели через User.create().
        """
        user = User.create(
            email=email,
            hashed_password=hashed_password,
            role=role,
            balance_credits=balance_credits,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)

        logger.info(
            "UserService.create: created user id=%s email=%s role=%s balance=%s",
            user.id,
            user.email,
            user.role,
            user.balance_credits,
        )
        return user

    async def get(self, session: AsyncSession, user_id: int) -> Optional[User]:
        """Получить пользователя по id."""
        user = await session.get(User, user_id)
        logger.info("UserService.get: user_id=%s found=%s", user_id, bool(user))
        return user

    async def get_by_email(self, session: AsyncSession, email: str) -> Optional[User]:
        """Получить пользователя по email."""
        res = await session.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()
        logger.info(
            "UserService.get_by_email: email=%s found=%s",
            email,
            bool(user),
        )
        return user

    async def list(
        self,
        session: AsyncSession,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[User]:
        """Список пользователей (постранично)."""
        res = await session.execute(
            select(User).order_by(User.id).offset(offset).limit(limit)
        )
        users = res.scalars().all()
        logger.info(
            "UserService.list: returned %s users (offset=%s, limit=%s)",
            len(users),
            offset,
            limit,
        )
        return users

    async def update(
        self,
        session: AsyncSession,
        user_id: int,
        **fields,
    ) -> Optional[User]:
        """
        Обновить произвольные поля пользователя.
        Например: role=UserRole.ADMIN, balance_credits=100 и т.п.
        """
        if not fields:
            logger.info("UserService.update: no fields to update (user_id=%s)", user_id)
            return await self.get(session, user_id)

        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(**fields)
        )
        await session.flush()

        user = await self.get(session, user_id)
        logger.info(
            "UserService.update: user_id=%s updated with %s (exists=%s)",
            user_id,
            fields,
            bool(user),
        )
        return user

    async def delete(self, session: AsyncSession, user_id: int) -> bool:
        """Удалить пользователя."""
        res = await session.execute(
            delete(User).where(User.id == user_id)
        )
        await session.flush()

        deleted = res.rowcount or 0
        logger.info(
            "UserService.delete: user_id=%s deleted=%s",
            user_id,
            bool(deleted),
        )
        return bool(deleted)

    async def change_balance_with_transaction(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        amount: int,
        tx_type: TransactionType,
        description: str,
    ) -> tuple[User, Transaction]:
        """
        Пополнение/списание баланса с созданием Transaction.

        amount — всегда положительный.
        tx_type=CREDIT -> баланс += amount
        tx_type=DEBIT -> баланс -= amount (с проверкой недостатка средств).
        """
        if amount <= 0:
            raise ValueError("Amount must be > 0 in change_balance_with_transaction")

        user = await self.get(session, user_id)
        if not user:
            raise ValueError(f"User id={user_id} not found")

        if tx_type == TransactionType.DEBIT and user.balance_credits < amount:
            raise ValueError(
                f"Not enough credits: have={user.balance_credits}, need={amount}"
            )

        old_balance = user.balance_credits

        if tx_type == TransactionType.CREDIT:
            user.balance_credits += amount
            tx = Transaction.create_credit(
                user_id=user.id,
                amount=amount,
                description=description,
            )
        else:
            user.balance_credits -= amount
            tx = Transaction.create_debit(
                user_id=user.id,
                amount=amount,
                description=description,
            )

        session.add(tx)

        await session.flush()
        await session.refresh(user)
        await session.refresh(tx)

        logger.info(
            "UserService.change_balance_with_transaction: user_id=%s "
            "type=%s amount=%s old_balance=%s new_balance=%s tx_id=%s",
            user.id,
            tx_type.value if hasattr(tx_type, "value") else tx_type,
            amount,
            old_balance,
            user.balance_credits,
            tx.id,
        )

        return user, tx


user_service = UserService()
