from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from .core.db import init_db, seed_initial_users, close_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tortodelova-backend")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Жизненный цикл приложения.

    При старте:
    - создаём таблицы в БД (если ещё нет);
    - сидим начальных пользователей (admin и test).

    При остановке:
    - корректно закрываем соединения с БД.
    """
    logger.info("Starting tortodelova backend...")

    # Инициализация БД и сидинг
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

    Здесь позже будут подключаться роутеры, middleware, CORS и т.д.
    """
    app = FastAPI(
        title="tortodelova ML Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["system"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app: FastAPI = create_app()


if __name__ == "__main__":
    """
    Команда для запуска:
    - uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
    """
    import uvicorn

    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port_raw = os.getenv("BACKEND_PORT", "8000")

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid BACKEND_PORT value: {port_raw!r}") from exc

    uvicorn.run(
        app,  # передаём сам объект приложения, чтобы не было проблем с импортами
        host=host,
        port=port,
        reload=True,
    )
