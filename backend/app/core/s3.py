from __future__ import annotations

import boto3
from botocore.client import Config

from app.core.config import get_settings

settings = get_settings()

# Базовая сессия boto3
_session = boto3.session.Session(
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    region_name=settings.s3_region,
)

# --- Внутренний клиент (для запросов из бэкенда к MinIO внутри docker-сети) ---
_s3_internal = _session.client(
    "s3",
    endpoint_url=settings.s3_endpoint,  # например: http://minio:9000
    config=Config(
        signature_version="s3v4",
        s3={
            "addressing_style": getattr(settings, "s3_addressing_style", "path"),
        },
    ),
)

# --- Клиент только для пресайнов (строим URL для браузера) ---
_presign_endpoint = getattr(settings, "s3_public_endpoint", None) or settings.s3_endpoint

_s3_presign = _session.client(
    "s3",
    endpoint_url=_presign_endpoint,
    config=Config(
        signature_version="s3v4",
        s3={
            "addressing_style": getattr(settings, "s3_addressing_style", "path"),
        },
    ),
)


def presigned_put(
    key: str,
    content_type: str = "application/octet-stream",
    expires: int = 3600,
) -> dict:
    """
    Пресайн на PUT. Content-Type должен совпасть с тем, что отправит клиент.
    """
    params = {
        "Bucket": settings.s3_bucket,
        "Key": key,
        "ContentType": content_type,
    }
    url = _s3_presign.generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=expires,
    )
    return {"url": url, "headers": {"Content-Type": content_type}}


def presigned_get(key: str, expires: int = 3600) -> dict:
    """
    Пресайн на GET для скачивания/просмотра в браузере.
    """
    params = {
        "Bucket": settings.s3_bucket,
        "Key": key,
    }
    url = _s3_presign.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires,
    )
    return {"url": url}


def read_object_bytes(key: str) -> bytes:
    """
    Чтение объекта из MinIO из бэкенда.
    """
    resp = _s3_internal.get_object(Bucket=settings.s3_bucket, Key=key)
    return resp["Body"].read()


def put_object_bytes(
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> dict:
    """
    Синхронная запись байт в MinIO из бэкенда (не через браузер).

    ВАЖНО:
    - гарантируем, что в Body уходит именно bytes;
    - явно выставляем ContentLength = len(data), чтобы не было рассинхрона
      и ошибок вида IncompleteBody.
    """
    # На всякий случай приводим к bytes
    if isinstance(data, memoryview):
        data = data.tobytes()
    elif not isinstance(data, (bytes, bytearray)):
        # Если вдруг сюда прилетит что-то ещё — явно конвертим, но не даём
        # уйти в странный стриминговый режим.
        data = bytes(data)

    length = len(data)

    _s3_internal.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
        ContentLength=length,
    )
    return {"key": key}


def copy_object(source_key: str, dest_key: str) -> dict:
    """
    Копирует объект внутри одного и того же бакета MinIO/S3.

    Используется StorageService.clone_prediction_image:
    - source_key: существующий ключ (например, user-1/predictions/xxx.png)
    - dest_key: новый ключ (например, user-2/predictions/yyy.png)
    """
    # На всякий случай уберём лидирующие слэши, чтобы не плодить разные формы одного ключа.
    source_key = source_key.lstrip("/")
    dest_key = dest_key.lstrip("/")

    _s3_internal.copy_object(
        Bucket=settings.s3_bucket,
        CopySource={
            "Bucket": settings.s3_bucket,
            "Key": source_key,
        },
        Key=dest_key,
    )

    return {
        "source_key": source_key,
        "dest_key": dest_key,
    }


def build_public_url(key: str) -> str:
    """
    Строит публичный URL для объекта по его ключу.

    Для MinIO в режиме path-style это:
        http://localhost:9000/<bucket>/<key>
    """
    base = (settings.s3_public_endpoint or settings.s3_endpoint).rstrip("/")
    key = key.lstrip("/")

    # Для path-style (MinIO по умолчанию)
    if getattr(settings, "s3_addressing_style", "path") == "path":
        return f"{base}/{settings.s3_bucket}/{key}"

    # Для virtual-host стиля предполагаем, что bucket уже зашит в base
    return f"{base}/{key}"
