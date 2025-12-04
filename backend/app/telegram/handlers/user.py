from __future__ import annotations

from typing import List

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.core.db import AsyncSessionLocal
from app.models.transaction import TransactionType
from app.services.repositories.user_service import user_service
from app.services.repositories.transaction_service import transaction_service
from app.telegram.handlers.auth import get_backend_user_id

router = Router(name="tg_user")


@router.message(Command("balance"))
async def cmd_balance(message: Message) -> None:
    """
    Показать текущий баланс пользователя.
    """
    backend_user_id = get_backend_user_id(message.from_user.id)
    if backend_user_id is None:
        await message.answer("Сначала выполните /register или /login.")
        return

    async with AsyncSessionLocal() as session:
        user = await user_service.get(session, backend_user_id)
        if not user:
            await message.answer(
                "Пользователь не найден. Попробуйте снова выполнить /login."
            )
            return

        await message.answer(f"Ваш баланс: <b>{user.balance_credits}</b> кредитов.")


@router.message(Command("deposit"))
async def cmd_deposit(message: Message) -> None:
    """
    Пополнить баланс на указанное количество кредитов.
    """
    backend_user_id = get_backend_user_id(message.from_user.id)
    if backend_user_id is None:
        await message.answer("Сначала выполните /register или /login.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: <code>/deposit 100</code>")
        return

    amount_str = parts[1].strip()
    try:
        amount = int(amount_str)
    except ValueError:
        await message.answer("Сумма должна быть целым числом.")
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return

    async with AsyncSessionLocal() as session:
        user = await user_service.get(session, backend_user_id)
        if not user:
            await message.answer(
                "Пользователь не найден. Попробуйте снова выполнить /login."
            )
            return

        try:
            user, _tx = await user_service.change_balance_with_transaction(
                session,
                user_id=user.id,
                amount=amount,
                tx_type=TransactionType.CREDIT,
                description="Пополнение через Telegram-бота",
            )
            await session.commit()
        except ValueError as exc:
            await session.rollback()
            await message.answer(f"Ошибка пополнения: {exc}")
            return

        await message.answer(
            f"Баланс пополнен на {amount} кредитов.\n"
            f"Текущий баланс: <b>{user.balance_credits}</b>."
        )


@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    """
    Показать последние транзакции пользователя.
    """
    backend_user_id = get_backend_user_id(message.from_user.id)
    if backend_user_id is None:
        await message.answer("Сначала выполните /register или /login.")
        return

    async with AsyncSessionLocal() as session:
        txs = await transaction_service.list_by_user(
            session,
            user_id=backend_user_id,
            limit=10,
            offset=0,
        )

    if not txs:
        await message.answer("У вас пока нет транзакций.")
        return

    lines: List[str] = ["Последние транзакции:"]
    for tx in txs:
        sign = "+" if tx.type == TransactionType.CREDIT else "-"
        lines.append(
            f"{tx.created_at:%Y-%m-%d %H:%M} — {sign}{tx.amount} "
            f"({tx.description or 'без описания'})"
        )

    await message.answer("\n".join(lines))
