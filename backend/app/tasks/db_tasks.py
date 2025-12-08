from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.celery_app import celery_app
from app.core.config import get_settings
from app.models.prediction import PredictionStatus
from app.models.transaction import TransactionType
from app.services.repositories.user_service import user_service
from app.services.repositories.prediction_service import prediction_service

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(
    name="app.tasks.db_tasks.save_prediction_result",
    queue="db_tasks",
    routing_key="db.save",
)
def save_prediction_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery-задача db_worker:

    - атомарно списывает кредиты с баланса пользователя;
    - создаёт PredictionRequest с SUCCESS статусом;
    - обеспечивает идемпотентность по celery_task_id.

    Ожидаемый payload:
    {
        "user_id": int,
        "prompt_ru": str,
        "prompt_en": str,
        "s3_key": str,
        "public_url": str,
        "credits_spent": int,
        "task_id": str,          # Celery task id (может быть None)
    }
    """

    async def _inner() -> Dict[str, Any]:
        # ВАЖНО: для каждой таски свой engine и свой event loop (через asyncio.run),
        # чтобы не было конфликтов "Future attached to a different loop".
        engine = create_async_engine(
            settings.db_url,
            echo=settings.db_echo,
        )
        SessionLocal = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

        try:
            async with SessionLocal() as session:  # type: AsyncSession
                user_id = int(payload["user_id"])
                credits_spent = int(payload["credits_spent"])
                task_id: Optional[str] = payload.get("task_id")

                logger.info(
                    "save_prediction_result: start (user_id=%s, credits_spent=%s, task_id=%s)",
                    user_id,
                    credits_spent,
                    task_id,
                )

                # ВАЖНО: НИКАКИХ запросов до session.begin() — иначе сработает autobegin.
                async with session.begin():
                    # 0. Идемпотентность по celery_task_id (если он передан)
                    if task_id:
                        existing = await prediction_service.get_by_task_id(
                            session=session,
                            task_id=task_id,
                        )
                        if existing:
                            logger.info(
                                "save_prediction_result: prediction already exists "
                                "(task_id=%s, prediction_id=%s, user_id=%s)",
                                task_id,
                                existing.id,
                                existing.user_id,
                            )
                            # Транзакция будет зафикшена (но изменений мы не делали)
                            return {
                                "prediction_id": existing.id,
                                "user_id": existing.user_id,
                                "public_url": existing.public_url,
                                "credits_spent": existing.credits_spent,
                                "status": existing.status.value,
                                "already_exists": True,
                            }

                    # 1. Списываем кредиты у пользователя
                    user, tx = await user_service.change_balance_with_transaction(
                        session=session,
                        user_id=user_id,
                        amount=credits_spent,
                        tx_type=TransactionType.DEBIT,
                        description="Image generation (Celery)",
                    )

                    logger.info(
                        "save_prediction_result: debited=%s (tx_id=%s) new_balance=%s",
                        tx.amount,
                        tx.id,
                        user.balance_credits,
                    )

                    # 2. Создаём PredictionRequest со статусом SUCCESS
                    prediction = await prediction_service.create(
                        session=session,
                        user_id=user_id,
                        prompt_ru=payload["prompt_ru"],
                        prompt_en=payload["prompt_en"],
                        s3_key=payload["s3_key"],
                        public_url=payload["public_url"],
                        credits_spent=credits_spent,
                        status=PredictionStatus.SUCCESS,
                        celery_task_id=task_id,
                    )

                    logger.info(
                        "save_prediction_result: prediction_id=%s user_id=%s status=%s",
                        prediction.id,
                        prediction.user_id,
                        prediction.status,
                    )

                # Здесь транзакция уже закоммичена
                return {
                    "prediction_id": prediction.id,
                    "user_id": prediction.user_id,
                    "public_url": prediction.public_url,
                    "credits_spent": prediction.credits_spent,
                    "status": prediction.status.value,
                }

        finally:
            # Гарантированно закрываем пул коннектов к БД в рамках этого event loop.
            await engine.dispose()

    return asyncio.run(_inner())
