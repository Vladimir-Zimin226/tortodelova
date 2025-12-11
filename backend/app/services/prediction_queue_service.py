from __future__ import annotations

import uuid
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

    Возвращает task_id, который потом будет сохранён в prediction_requests.celery_task_id.
    """
    task_id = str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "user_id": user_id,
        "prompt_ru": prompt_ru,
        "credits_spent": credits_spent,
        "task_id": task_id,
    }

    run_image_generation.apply_async(
        kwargs={"payload": payload},
        queue="ml_tasks",
        routing_key="ml.generate",
        task_id=task_id,
    )

    return task_id
