from __future__ import annotations

from typing import Any, Dict, Optional

from app.tasks.ml_tasks import run_image_generation


def enqueue_image_generation(
    *,
    user_id: int,
    prompt_ru: str,
    credits_spent: int,
    tg_chat_id: Optional[int] = None,
) -> str:
    """
    Поставить задачу на генерацию изображения в очередь Celery.

    """
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "prompt_ru": prompt_ru,
        "credits_spent": credits_spent,
    }

    if tg_chat_id is not None:
        payload["tg_chat_id"] = tg_chat_id

    result = run_image_generation.apply_async(
        kwargs={"payload": payload},
        queue="ml_tasks",
        routing_key="ml.generate",
    )

    return result.id