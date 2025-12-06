from __future__ import annotations

import asyncio
import logging
from typing import Tuple
from uuid import uuid4

from app.core.s3 import put_object_bytes, build_public_url

logger = logging.getLogger(__name__)


class StorageService:
    """
    Сервис для сохранения изображений в S3/MinIO.

    - принимает байты изображения;
    - пишет объект в бакет через boto3 (MinIO);
    - формирует s3_key и public_url.

    """

    def __init__(self) -> None:
        # пока без параметров, но оставляем конструктор на будущее
        ...

    async def save_prediction_image(self, image_bytes: bytes, user_id: int) -> Tuple[str, str]:
        """
        Сохраняет байты изображения и возвращает (s3_key, public_url).

        s3_key — относительный путь внутри бакета;
        public_url — полноценный HTTP-URL, по которому можно скачать картинку.
        """
        if not image_bytes:
            raise ValueError("Пустой image_bytes сохранять нельзя.")

        # Простой и удобный формат ключа
        object_name = f"{uuid4().hex}.png"
        s3_key = f"user-{user_id}/predictions/{object_name}"

        def _upload() -> None:
            put_object_bytes(
                key=s3_key,
                data=image_bytes,
                content_type="image/png",
            )

        await asyncio.to_thread(_upload)

        public_url = build_public_url(s3_key)

        logger.info(
            "StorageService.save_prediction_image: stored to s3_key=%s (public_url=%s)",
            s3_key,
            public_url,
        )

        return s3_key, public_url


storage_service = StorageService()
