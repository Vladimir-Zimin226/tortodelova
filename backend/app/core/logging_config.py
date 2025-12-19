from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


_CONFIGURED = False


def _parse_level(level: str) -> int:
    level_upper = (level or "INFO").upper()
    return getattr(logging, level_upper, logging.INFO)


def setup_logging(
    *,
    service_name: Optional[str] = None,
    level: Optional[str] = None,
    log_dir: Optional[str] = None,
) -> None:
    """
    Единая настройка логирования для всего приложения (uvicorn/fastapi/celery).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    service = service_name or os.getenv("SERVICE_NAME", "app")
    log_level = _parse_level(level or os.getenv("LOG_LEVEL", "INFO"))
    logs_path = Path(log_dir or os.getenv("LOG_DIR", "/app/logs"))
    logs_path.mkdir(parents=True, exist_ok=True)

    # Файл логов на сервис (backend/ml_worker/db_worker)
    file_path = logs_path / f"{service}.log"

    max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10MB
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    fmt = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    formatter = logging.Formatter(fmt)

    # Корневой логгер
    root = logging.getLogger()
    root.setLevel(log_level)

    root.handlers.clear()

    # Console
    sh = logging.StreamHandler()
    sh.setLevel(log_level)
    sh.setFormatter(formatter)

    # File
    fh = RotatingFileHandler(
        filename=str(file_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    fh.setLevel(log_level)
    fh.setFormatter(formatter)

    root.addHandler(sh)
    root.addHandler(fh)

    # Uvicorn
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(logger_name)
        lg.setLevel(log_level)
        lg.propagate = True  # пусть уходит в root handlers

    # Celery/Kombu/AMQP
    for logger_name in ("celery", "kombu", "amqp"):
        lg = logging.getLogger(logger_name)
        lg.setLevel(log_level)
        lg.propagate = True

    _CONFIGURED = True


def get_logger(
    logger_name: str = "default logger",
    level: Optional[int] = None,
) -> logging.Logger:
    """
    Возвращает настроенный логгер.
    """
    setup_logging()
    logger = logging.getLogger(logger_name)
    if level is not None:
        logger.setLevel(level)
    return logger
