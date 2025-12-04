from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)

# Переопределим через app.env при переходе на MinIO когда подключим реальные ML-модели
S3_PUBLIC_ENDPOINT = os.getenv("S3_PUBLIC_ENDPOINT", "http://localhost:9000")
S3_BUCKET = os.getenv("S3_BUCKET", "tortodelova")


class StorageService:
    """
    Сервис для сохранения изображений.

    Сейчас:
    - сохраняет байты на локальный диск в каталоге /app/data/images;
    - формирует s3_key и public_url, как если бы это был S3/MinIO.

    Позже заменим внутреннюю реализацию на MinIO-клиент,
    не меняя интерфейс метода save_prediction_image.
    """

    def __init__(self, base_dir: str = "/app/data/images") -> None:
        self.base_dir = Path(base_dir)

    async def save_prediction_image(self, image_bytes: bytes, user_id: int) -> Tuple[str, str]:
        """
        Сохраняет байты изображения и возвращает (s3_key, public_url).

        s3_key — относительный путь внутри "бакета";
        public_url — {S3_PUBLIC_ENDPOINT}/{S3_BUCKET}/{s3_key}
        """
        if not image_bytes:
            raise ValueError("Пустой image_bytes сохранять нельзя.")

        # Простейший формат ключа
        s3_key = f"user-{user_id}/{uuid4().hex}.bin"

        full_path = self.base_dir / s3_key
        full_path.parent.mkdir(parents=True, exist_ok=True)

        def _write_file() -> None:
            with open(full_path, "wb") as f:
                f.write(image_bytes)

        await asyncio.to_thread(_write_file)

        public_url = f"{S3_PUBLIC_ENDPOINT.rstrip('/')}/{S3_BUCKET}/{s3_key}"
        logger.info(
            "StorageService.save_prediction_image: saved to %s (public_url=%s)",
            full_path,
            public_url,
        )

        return s3_key, public_url


storage_service = StorageService()
