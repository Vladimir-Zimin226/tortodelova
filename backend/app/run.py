from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.db import init_db, seed_initial_users, seed_initial_ml_models, close_db
from app.api.routes import auth, user, predictions
from app.api.routes.admin import router as admin_router

try:
    from app.core.config import settings  # type: ignore[attr-defined]
except ImportError:
    from app.core.config import Settings  # type: ignore[import-not-found]

    settings = Settings()  # type: ignore[call-arg]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tortodelova-backend")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting tortodelova backend...")

    await init_db()
    await seed_initial_users()
    await seed_initial_ml_models()

    try:
        yield
    finally:
        await close_db()
        logger.info("Shutting down tortodelova backend...")


def create_app() -> FastAPI:
    app = FastAPI(
        title=getattr(settings, "APP_NAME", "tortodelova ML Service"),
        description=getattr(settings, "APP_DESCRIPTION", "Tortodelova ML backend"),
        version=getattr(settings, "API_VERSION", "0.1.0"),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    # Подключаем роутеры:
    app.include_router(auth.router)
    app.include_router(user.router)
    app.include_router(predictions.router)
    app.include_router(admin_router)

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
        app,
        host=host,
        port=port,
        reload=True,
    )
