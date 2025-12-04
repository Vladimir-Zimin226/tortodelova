from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from app.core.config import get_settings
from app.telegram.handlers import auth, user, predictions


async def main() -> None:
    """
    Точка входа для запуска Telegram-бота.

    Запуск (из контейнера):
    python -m app.telegram.bot
    """
    settings = get_settings()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    # Регистрируем роутеры с хэндлерами
    dp.include_router(auth.router)
    dp.include_router(user.router)
    dp.include_router(predictions.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
