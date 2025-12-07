from __future__ import annotations

import logging
from typing import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.base import Base
from app.models.user import User, UserRole
from app.models.transaction import Transaction          # noqa: F401
from app.models.prediction import PredictionRequest     # noqa: F401
from app.models.ml_model import MLModel, MLModelType    # noqa: F401

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

async def seed_initial_ml_models() -> None:
    """
    Одноразовый сидинг базовых ML-моделей:
    - переводчик RU->EN;
    - модель генерации изображений DreamShaper.

    Срабатывает только если таблица ml_models пустая.
    """
    async with AsyncSessionLocal() as session:
        logger.info("Checking if initial ML models need to be seeded...")
        from sqlalchemy import select  # уже импортирован выше, но на всякий случай

        res = await session.execute(select(MLModel).limit(1))
        existing = res.scalars().first()
        if existing:
            logger.info("ML models already exist, skipping seeding.")
            return

        logger.info("Seeding initial ML models...")

        # Переводчик RU->EN (Helsinki-NLP opus-mt-ru-en)
        translator = MLModel.create(
            name="opus-mt-ru-en",
            display_name="Helsinki-NLP opus-mt-ru-en (RU→EN)",
            model_type=MLModelType.TRANSLATION,
            engine="huggingface",
            version=None,
            cost_credits=0,
            is_active=True,
        )

        # Модель генерации изображений (DreamShaper v8)
        dreamshaper = MLModel.create(
            name="dreamshaper_v8",
            display_name="DreamShaper v8 (SD 1.5)",
            model_type=MLModelType.IMAGE_GENERATION,
            engine="diffusers",
            version="v8",
            cost_credits=10,  # можно поменять по своему тарифу
            is_active=True,
        )

        session.add_all([translator, dreamshaper])
        await session.commit()

        logger.info(
            "Seeded ML models: translator=%s, image_model=%s",
            translator.name,
            dreamshaper.name,
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
