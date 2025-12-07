from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.core.db import AsyncSessionLocal
from app.models.prediction import PredictionStatus
from app.models.transaction import TransactionType
from app.services.repositories.user_service import user_service
from app.services.repositories.prediction_service import prediction_service

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.db_tasks.save_prediction_result",
    queue="db_tasks",
    routing_key="db.save",
)
def save_prediction_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery-задача второго воркера: атомарно списывает кредиты и создаёт PredictionRequest.

    Ожидаемый payload:
        {
            "user_id": int,
            "prompt_ru": str,
            "prompt_en": str,
            "s3_key": str,
            "public_url": str,
            "credits_spent": int,
        }
    """

    async def _inner() -> Dict[str, Any]:
        async with AsyncSessionLocal() as session:  # type: AsyncSession
            async with session.begin():
                user_id = int(payload["user_id"])
                credits_spent = int(payload["credits_spent"])

                logger.info(
                    "save_prediction_result: user_id=%s credits_spent=%s",
                    user_id,
                    credits_spent,
                )

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
                )

            logger.info(
                "save_prediction_result: prediction_id=%s user_id=%s status=%s",
                prediction.id,
                prediction.user_id,
                prediction.status,
            )

            return {
                "prediction_id": prediction.id,
                "user_id": prediction.user_id,
                "public_url": prediction.public_url,
                "credits_spent": prediction.credits_spent,
                "status": prediction.status.value,
            }

    return asyncio.run(_inner())
