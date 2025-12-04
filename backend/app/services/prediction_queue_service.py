from __future__ import annotations

from typing import Any, Dict

from app.tasks.ml_tasks import run_image_generation


def enqueue_image_generation(
    *,
    user_id: int,
    prompt_ru: str,
    credits_spent: int,
) -> str:
    """
    Поставить задачу на генерацию изображения в очередь Celery.

    Возвращает task_id Celery, который можно логировать / отдавать клиенту.
    """
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "prompt_ru": prompt_ru,
        "credits_spent": credits_spent,
    }

    result = run_image_generation.apply_async(
        kwargs={"payload": payload},
        queue="ml_tasks",
        routing_key="ml.generate",
    )

    return result.id
