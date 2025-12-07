from __future__ import annotations

# Импортируем задачи, чтобы autodiscover в Celery их точно увидел.
from . import ml_tasks  # noqa: F401
from . import db_tasks  # noqa: F401
