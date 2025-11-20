from __future__ import annotations

import logging
from typing import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_settings
from .security import hash_password
from backend.app.models.base import Base
from backend.app.models.user import User, UserRole

logger = logging.getLogger("tortodelova-db")

settings = get_settings()

# Async engine для работы с Postgres
engine = create_async_engine(
    settings.db_url,
    echo=settings.db_echo,
    future=True,
)

# Фабрика асинхронных сессий
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def init_db() -> None:
    """
    Создаёт все таблицы в БД согласно ORM-моделям.

    Вызывается при старте приложения. В дальнейшем вместо этого лучше
    использовать миграции (Alembic), но для ранней стадии разработки
    автосоздание таблиц удобно.
    """
    logger.info("Creating database tables (if not exist)...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables are ready.")


async def seed_initial_users() -> None:
    """
    Одноразовый сидинг пользователей: admin и test.

    - Срабатывает только если таблица `users` пустая.
    - Данные берутся из переменных окружения:
      SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD
      SEED_USER_EMAIL  / SEED_USER_PASSWORD
    """
    async with AsyncSessionLocal() as session:
        # Проверяем, есть ли уже хоть один пользователь
        logger.info("Checking if initial users need to be seeded...")
        res = await session.execute(select(User).limit(1))
        existing = res.scalars().first()
        if existing:
            logger.info("Users already exist, skipping seeding.")
            return

        logger.info("Seeding initial users (admin and test)...")

        admin = User.create(
            email=settings.seed_admin_email,
            hashed_password=hash_password(settings.seed_admin_password),
            role=UserRole.ADMIN,
        )

        common_user = User.create(
            email=settings.seed_user_email,
            hashed_password=hash_password(settings.seed_user_password),
            role=UserRole.USER,
        )

        session.add_all([admin, common_user])
        await session.commit()

        logger.info(
            "Seeded users: admin=%s, user=%s",
            settings.seed_admin_email,
            settings.seed_user_email,
        )


async def get_db() -> AsyncIterator[AsyncSession]:
    """
    Dependency для FastAPI (будет использоваться в роутерах).

    Пример:
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session


async def close_db() -> None:
    """
    Корректно закрывает engine при завершении работы приложения.
    """
    await engine.dispose()
