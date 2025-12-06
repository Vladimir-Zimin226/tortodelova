from __future__ import annotations

import logging

from celery import Celery
from kombu import Exchange, Queue

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "tortodelova",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Настройка очередей:
# - ml_tasks: задачи на перевод/генерацию/загрузку в MinIO
# - db_tasks: задачи на запись результатов в БД
default_exchange = Exchange("tortodelova", type="topic")

celery_app.conf.update(
    task_default_exchange=default_exchange.name,
    task_default_exchange_type=default_exchange.type,
    task_default_queue="ml_tasks",
    task_default_routing_key="ml.default",
    task_queues=(
        Queue(
            "ml_tasks",
            default_exchange,
            routing_key="ml.#",
        ),
        Queue(
            "db_tasks",
            default_exchange,
            routing_key="db.#",
        ),
    ),
    task_time_limit=300,        # защита от зависших задач
    task_soft_time_limit=240,
)

# Авто-поиск задач в пакете app.tasks
celery_app.autodiscover_tasks(
    [
        "app.tasks",
    ]
)

logger.info(
    "Celery app initialized with broker=%s backend=%s",
    settings.celery_broker_url,
    settings.celery_result_backend,
)
