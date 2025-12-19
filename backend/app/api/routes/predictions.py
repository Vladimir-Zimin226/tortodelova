from __future__ import annotations

import logging
import asyncio
import os

from botocore.exceptions import ClientError
from typing import List, Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.s3 import presigned_get, get_object_stream
from app.core.config import get_settings
from app.models.user import User
from app.models.ml_model import MLModelType
from app.services.repositories.user_service import user_service
from app.services.repositories.prediction_service import prediction_service
from app.services.repositories.ml_model_service import ml_model_service
from app.api.routes.auth import get_current_user
from app.services.prediction_queue_service import enqueue_image_generation

from app.api.schemas.predictions import (
    PredictionCreateRequest,
    PredictionOut,
    PredictionEnqueueResponse,
    DemoClaimRequest,
    MessageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/predictions",
    tags=["predictions"],
)

settings = get_settings()


@router.post(
    "",
    response_model=PredictionEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_prediction(
    payload: PredictionCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PredictionEnqueueResponse:
    """
    POST /api/predictions
    """
    # 1) Выбираем ML-модель
    if payload.model_id and payload.model_id > 0:
        ml_model = await ml_model_service.get(session, payload.model_id)
        if not ml_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ML model not found",
            )

        # ВАЖНО: сначала проверяем тип (для теста wrong_type)
        if ml_model.model_type != MLModelType.IMAGE_GENERATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified model is not an image generation model",
            )

        # ВАЖНО: затем проверяем активность (чтобы НЕ дергать Celery при is_active=False)
        if not getattr(ml_model, "is_active", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified model is not active",
            )
    else:
        # первая активная image-модель
        ml_models = await ml_model_service.list(
            session,
            model_type=MLModelType.IMAGE_GENERATION,
            is_active=True,
            limit=1,
            offset=0,
        )
        if not ml_models:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No active image generation model configured",
            )
        ml_model = ml_models[0]

    cost = ml_model.cost_credits

    # 2) Проверяем баланс
    if current_user.balance_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not enough credits: need={cost}, have={current_user.balance_credits}",
        )

    # 3) Ставим задачу в очередь Celery
    task_id = enqueue_image_generation(
        user_id=current_user.id,
        prompt_ru=payload.prompt,
        credits_spent=cost,
    )

    return PredictionEnqueueResponse(
        task_id=task_id,
        queued=True,
        cost_credits=cost,
        message="Prediction request queued",
    )


@router.get(
    "",
    response_model=List[PredictionOut],
)
async def list_predictions(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[PredictionOut]:
    """
    GET /api/predictions
    """
    items = await prediction_service.list_by_user(
        session,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return list(items)


@router.get(
    "/{prediction_id}",
    response_model=PredictionOut,
)
async def get_prediction_by_id(
    prediction_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PredictionOut:
    """
    GET /api/predictions/{id}
    """
    prediction = await prediction_service.get(session, prediction_id)
    if not prediction or prediction.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found",
        )
    return prediction


@router.get(
    "/{prediction_id}/image",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def get_prediction_image(
    prediction_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """
    GET /api/predictions/{id}/image
    """
    prediction = await prediction_service.get(session, prediction_id)
    if not prediction or prediction.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found",
        )

    if not prediction.s3_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image key is not available for this prediction",
        )

    presigned = presigned_get(prediction.s3_key, expires=3600)
    url = presigned["url"]
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get(
    "/{prediction_id}/download",
)
async def download_prediction_image(
    prediction_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    GET /api/predictions/{id}/download

    Стримит файл из MinIO через бэкенд и отдаёт как attachment,
    чтобы браузер гарантированно скачивал.
    """
    prediction = await prediction_service.get(session, prediction_id)
    if not prediction or prediction.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found",
        )

    if not prediction.s3_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image key is not available for this prediction",
        )

    try:
        body, content_type, content_length = await asyncio.to_thread(
            get_object_stream,
            prediction.s3_key,
        )
    except ClientError:
        # объект мог быть удалён/не найден в бакете
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found in storage",
        )

    filename = f"prediction-{prediction_id}{os.path.splitext(prediction.s3_key)[1] or '.png'}"

    def iterfile() -> Iterator[bytes]:
        try:
            while True:
                chunk = body.read(1024 * 1024)  # 1MB
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                body.close()
            except Exception:
                pass

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    }
    if content_length is not None:
        headers["Content-Length"] = str(content_length)

    return StreamingResponse(
        iterfile(),
        media_type=content_type or "image/png",
        headers=headers,
    )


@router.get("/demo/{task_id}", response_model=PredictionOut)
async def demo_prediction_preview(
    task_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PredictionOut:
    """
    Вернуть demo prediction по task_id, если он принадлежит demo-пользователю (DEMO_EMAIL).
    """
    demo_user = await user_service.get_by_email(session, settings.demo_email)
    if not demo_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo user not found",
        )

    prediction = await prediction_service.get_by_task_id(session, task_id=task_id)
    if not prediction or prediction.user_id != demo_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo prediction not found",
        )

    return prediction


@router.post("/demo/claim", response_model=MessageResponse)
async def demo_prediction_claim(
    payload: DemoClaimRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Клонирует demo prediction (из demo-пользователя) в историю текущего пользователя.
    """
    demo_user = await user_service.get_by_email(session, settings.demo_email)
    if not demo_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo user not found",
        )

    demo_pred = await prediction_service.get_by_task_id(session, task_id=payload.task_id)
    if not demo_pred or demo_pred.user_id != demo_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo prediction not found",
        )

    cloned = await prediction_service.clone_demo_prediction_for_user(
        session,
        task_id=payload.task_id,
        new_user=current_user,
    )
    if not cloned:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo prediction not found",
        )

    await session.commit()
    return MessageResponse(message="Демо-предсказание добавлено в вашу историю")

