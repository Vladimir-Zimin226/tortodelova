from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from app.celery_app import celery_app
from app.services.ml_service import ml_service
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.ml_tasks.run_image_generation",
    queue="ml_tasks",
    routing_key="ml.generate",
)
def run_image_generation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery-задача первого воркера: перевод, генерация изображения и сохранение в хранилище.

    Ожидаемый payload:
        {
            "user_id": int,
            "prompt_ru": str,
            "credits_spent": int,
        }

    Возвращает словарь с данными для записи результата в БД и
    отдельно ставит задачу второго воркера (save_prediction_result).
    """

    async def _inner() -> Dict[str, Any]:
        user_id = int(payload["user_id"])
        prompt_ru = str(payload["prompt_ru"])
        credits_spent = int(payload["credits_spent"])

        logger.info(
            "run_image_generation: user_id=%s credits_spent=%s",
            user_id,
            credits_spent,
        )

        # 1. Перевод RU -> EN
        prompt_en = await ml_service.translate_ru_to_en(prompt_ru)
        logger.debug("run_image_generation: translated prompt_en=%s", prompt_en)

        # 2. Генерация изображения (байты)
        image_bytes = await ml_service.generate_image(prompt_en)
        logger.info(
            "run_image_generation: image generated for user_id=%s (size=%s bytes)",
            user_id,
            len(image_bytes),
        )

        # 3. Сохранение в хранилище (сейчас — локальное FS + формирование s3_key/public_url)
        s3_key, public_url = await storage_service.save_prediction_image(
            image_bytes=image_bytes,
            user_id=user_id,
        )
        logger.info(
            "run_image_generation: image stored with s3_key=%s public_url=%s",
            s3_key,
            public_url,
        )

        result_payload: Dict[str, Any] = {
            "user_id": user_id,
            "prompt_ru": prompt_ru,
            "prompt_en": prompt_en,
            "s3_key": s3_key,
            "public_url": public_url,
            "credits_spent": credits_spent,
        }

        # 4. Поставить отдельную задачу на запись в БД
        from app.tasks.db_tasks import save_prediction_result

        save_prediction_result.apply_async(
            kwargs={"payload": result_payload},
            queue="db_tasks",
            routing_key="db.save",
        )

        return result_payload

    return asyncio.run(_inner())
