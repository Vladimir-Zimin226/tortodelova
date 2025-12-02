from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.db import init_db, seed_initial_users, close_db
from app.api.routes import auth, user, predictions

try:
    from app.core.config import settings  # type: ignore[attr-defined]
except ImportError:
    from app.core.config import Settings  # type: ignore[import-not-found]

    settings = Settings()  # type: ignore[call-arg]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tortodelova-backend")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Жизненный цикл приложения.

    При старте:
    - создаём таблицы в БД (если ещё нет);
    - сидируем начальных пользователей (admin и test).

    При остановке:
    - корректно закрываем соединения с БД.
    """
    logger.info("Starting tortodelova backend...")

    await init_db()
    await seed_initial_users()

    try:
        yield
    finally:
        await close_db()
        logger.info("Shutting down tortodelova backend...")


def create_app() -> FastAPI:
    """
    Фабрика приложения FastAPI.

    Здесь подключаются lifespan, CORS, системные эндпоинты
    и настройки Swagger/Redoc.
    """
    app = FastAPI(
        title=getattr(settings, "APP_NAME", "tortodelova ML Service"),
        description=getattr(settings, "APP_DESCRIPTION", "Tortodelova ML backend"),
        version=getattr(settings, "API_VERSION", "0.1.0"),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # Базовая CORS-конфигурация.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    async def health_check() -> dict[str, str]:
        """
        Эндпоинт для проверки живости контейнера.
        Используется Docker healthcheck'ом.
        """
        return {"status": "ok"}

    # Здесь подключаем роутеры API:
    app.include_router(auth.router)
    app.include_router(user.router)
    app.include_router(predictions.router)

    return app

app: FastAPI = create_app()


if __name__ == "__main__":
    """
    Локальный запуск:
      python -m app.api
    или
      uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
    """
    import uvicorn

    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port_raw = os.getenv("BACKEND_PORT", "8000")

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid BACKEND_PORT value: {port_raw!r}") from exc

    uvicorn.run(
        app,  # передаём сам объект приложения
        host=host,
        port=port,
        reload=True,
    )
