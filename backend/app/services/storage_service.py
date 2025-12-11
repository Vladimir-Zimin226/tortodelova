from __future__ import annotations

import asyncio
import logging
from typing import Tuple
from uuid import uuid4

from app.core.s3 import put_object_bytes, build_public_url, copy_object

logger = logging.getLogger(__name__)


class StorageService:
    """
    Сервис для сохранения и клонирования изображений в S3/MinIO.

    - принимает байты изображения;
    - пишет объект в бакет через boto3 (MinIO);
    - формирует s3_key и public_url;
    - умеет клонировать уже существующий объект под новым ключом.
    """

    def __init__(self) -> None:
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

        # Запись в S3 делаем в отдельном треде, чтобы не блокировать event loop
        await asyncio.to_thread(_upload)

        public_url = build_public_url(s3_key)

        logger.info(
            "StorageService.save_prediction_image: stored to s3_key=%s (public_url=%s)",
            s3_key,
            public_url,
        )

        return s3_key, public_url

    async def clone_prediction_image(
        self,
        *,
        source_s3_key: str,
        target_user_id: int,
    ) -> Tuple[str, str]:
        """
        Клонирует существующий объект в S3 под новым ключом в пространстве target_user_id.

        ВАЖНО: создаётся реальный новый объект и новый s3_key,
        так что уникальный индекс по s3_key в БД не нарушается.

        Возвращает (new_s3_key, new_public_url).
        """
        if not source_s3_key:
            raise ValueError("source_s3_key обязателен для клонирования.")

        new_filename = f"{uuid4().hex}.png"
        new_s3_key = f"user-{target_user_id}/predictions/{new_filename}"

        def _copy() -> Tuple[str, str]:
            copy_object(source_key=source_s3_key, dest_key=new_s3_key)
            public_url = build_public_url(new_s3_key)
            return new_s3_key, public_url

        new_s3_key_result, new_public_url = await asyncio.to_thread(_copy)

        logger.info(
            "StorageService.clone_prediction_image: %s -> %s (user_id=%s)",
            source_s3_key,
            new_s3_key_result,
            target_user_id,
        )

        return new_s3_key_result, new_public_url


storage_service = StorageService()
