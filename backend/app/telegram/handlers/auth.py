from __future__ import annotations

from typing import Dict

from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from ...core.db import AsyncSessionLocal
from ...core.security import hash_password, verify_password
from ...models.user import UserRole
from ...services.repositories.user_service import user_service

router = Router(name="tg_auth")

# Простое in-memory соответствие Telegram user_id -> backend user_id.
# Для production-версии лучше хранить это в БД.
telegram_sessions: Dict[int, int] = {}


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    text = (
        "Привет! 👋\n\n"
        "Я бот для доступа к ML-сервису tortodelova.\n\n"
        "Доступные команды:\n"
        "/register – регистрация (email + пароль)\n"
        "/login – авторизация\n"
        "/balance – текущий баланс\n"
        "/deposit – пополнить баланс\n"
        "/history – история транзакций\n"
        "/predict – создать запрос на генерацию\n"
        "/predictions – история запросов на генерации\n"
        "/prediction – детали конкретного запроса на генерацию\n\n"
        "Сначала зарегистрируйся с помощью /register и укажи свой email и пароль 🙂"
    )
    await message.answer(text)


@router.message(Command("register"))
async def cmd_register(message: Message) -> None:
    """
    Регистрация нового пользователя по email и паролю.
    """
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: <code>/register email@example.com пароль</code>")
        return

    _, email, password = parts

    async with AsyncSessionLocal() as session:
        existing = await user_service.get_by_email(session, email)
        if existing:
            await message.answer(
                "Пользователь с таким email уже существует. Используйте /login."
            )
            return

        hashed = hash_password(password)
        user = await user_service.create(
            session,
            email=email,
            hashed_password=hashed,
            role=UserRole.USER,
        )
        await session.commit()

        telegram_sessions[message.from_user.id] = user.id
        await message.answer(
            f"Вы зарегистрированы как <b>{user.email}</b>.\n"
            "Теперь вы можете использовать команды бота."
        )


@router.message(Command("login"))
async def cmd_login(message: Message) -> None:
    """
    Авторизация существующего пользователя по email и паролю.
    """
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: <code>/login email@example.com пароль</code>")
        return

    _, email, password = parts

    async with AsyncSessionLocal() as session:
        user = await user_service.get_by_email(session, email)
        if not user or not verify_password(password, user.hashed_password):
            await message.answer("Неверный email или пароль.")
            return

        telegram_sessions[message.from_user.id] = user.id
        await message.answer(f"Вы вошли как <b>{user.email}</b>.")


def get_backend_user_id(tg_user_id: int) -> int | None:
    """
    Получить id пользователя в БД по Telegram user_id.
    Возвращает None, если пользователь не аутентифицирован.
    """
    return telegram_sessions.get(tg_user_id)
