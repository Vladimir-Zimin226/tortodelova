from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

import requests

from app.celery_app import celery_app
from app.core.config import get_settings
from app.services.ml_service import ml_service
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

settings = get_settings()
BOT_TOKEN = settings.bot_token
TELEGRAM_API_BASE = (
    f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None
)


def _send_telegram_image(
    tg_chat_id: int,
    image_bytes: bytes,
    prompt_ru: str,
    public_url: str | None = None,
) -> None:
    """
    Отправить сгенерированное изображение в Telegram-чат как photo.

    """
    if not TELEGRAM_API_BASE:
        logger.warning(
            "Telegram BOT_TOKEN is not configured, skip sending image"
        )
        return

    if not tg_chat_id:
        logger.warning("tg_chat_id is empty or zero, skip sending image")
        return

    caption_lines = [
        "Готова картинка по вашему запросу ✅",
        f"Промпт: {prompt_ru}",
    ]
    if public_url:
        caption_lines.append(f"Ссылка: {public_url}")
    caption = "\n".join(caption_lines)

    try:
        resp = requests.post(
            f"{TELEGRAM_API_BASE}/sendPhoto",
            data={
                "chat_id": tg_chat_id,
                "caption": caption,
            },
            files={
                # имя файла условное, Telegram всё равно
                "photo": ("image.png", image_bytes),
            },
            timeout=60,
        )
        resp.raise_for_status()
        logger.info(
            "Sent Telegram image notification to chat_id=%s", tg_chat_id
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to send Telegram image notification to chat_id=%s",
            tg_chat_id,
        )


@celery_app.task(
    name="app.tasks.ml_tasks.run_image_generation",
    queue="ml_tasks",
    routing_key="ml.generate",
    soft_time_limit=600,
    time_limit=660,
)
def run_image_generation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery-задача первого воркера: перевод, генерация изображения и сохранение в хранилище.

    Ожидаемый payload:
        {
            "user_id": int,
            "prompt_ru": str,
            "credits_spent": int,
            "tg_chat_id": int,  # чат, куда вернуть результат
        }

    Возвращает словарь с данными для записи результата в БД и
    отдельно ставит задачу второго воркера (save_prediction_result).
    """

    async def _inner() -> Dict[str, Any]:
        user_id = int(payload["user_id"])
        prompt_ru = str(payload["prompt_ru"])
        credits_spent = int(payload["credits_spent"])
        tg_chat_id = payload.get("tg_chat_id")

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

        # 3. Сохранение в хранилище (локальное FS + формирование s3_key/public_url)
        s3_key, public_url = await storage_service.save_prediction_image(
            image_bytes=image_bytes,
            user_id=user_id,
        )
        logger.info(
            "run_image_generation: image stored with s3_key=%s public_url=%s",
            s3_key,
            public_url,
        )

        # 3.1. Отправляем картинку в Telegram-чат
        if tg_chat_id is not None:
            _send_telegram_image(
                tg_chat_id=int(tg_chat_id),
                image_bytes=image_bytes,
                prompt_ru=prompt_ru,
                public_url=public_url,
            )
        else:
            logger.info(
                "tg_chat_id is not provided in payload, skip Telegram sending"
            )

        result_payload: Dict[str, Any] = {
            "user_id": user_id,
            "prompt_ru": prompt_ru,
            "prompt_en": prompt_en,
            "s3_key": s3_key,
            "public_url": public_url,
            "credits_spent": credits_spent,
            "tg_chat_id": tg_chat_id,
        }

        # 4. Ставим отдельную задачу на запись в БД
        from app.tasks.db_tasks import save_prediction_result

        save_prediction_result.apply_async(
            kwargs={"payload": result_payload},
            queue="db_tasks",
            routing_key="db.save",
        )

        return result_payload

    return asyncio.run(_inner())
