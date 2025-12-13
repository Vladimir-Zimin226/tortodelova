from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, constr, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.s3 import presigned_get
from app.core.config import get_settings
from app.models.user import User
from app.models.ml_model import MLModelType
from app.services.repositories.user_service import user_service
from app.services.repositories.prediction_service import prediction_service
from app.services.repositories.ml_model_service import ml_model_service
from app.api.routes.auth import get_current_user
from app.services.prediction_queue_service import enqueue_image_generation

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/predictions",
    tags=["predictions"],
)

settings = get_settings()

class PredictionCreateRequest(BaseModel):
    prompt: constr(min_length=1)
    # Если None или <= 0 — берём первую активную image-модель
    model_id: Optional[int] = None


class PredictionOut(BaseModel):
    id: int
    prompt_ru: str
    prompt_en: str
    s3_key: str
    public_url: str
    credits_spent: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PredictionEnqueueResponse(BaseModel):
    task_id: str
    queued: bool = True
    cost_credits: int
    message: str

class DemoClaimRequest(BaseModel):
  task_id: str


class MessageResponse(BaseModel):
  message: str

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

    Эндпоинт НЕ выполняет генерацию синхронно, а:
    - выбирает активную image-модель (или конкретную по model_id);
    - проверяет баланс пользователя;
    - ставит задачу в очередь Celery (ml_tasks);
    - возвращает task_id и информацию о том, что задача поставлена.

    Фактическая генерация и запись в БД выполняются воркерами:
    - ml-worker: перевод + генерация картинки + сохранение в S3/MinIO;
    - db-worker: списание кредитов + создание PredictionRequest.
    """

    # 1. Выбираем ML-модель
    if payload.model_id and payload.model_id > 0:
        ml_model = await ml_model_service.get(session, payload.model_id)
        if not ml_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ML model not found",
            )
        if ml_model.model_type != MLModelType.IMAGE_GENERATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified model is not an image generation model",
            )
        if not ml_model.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified model is not active",
            )
    else:
        models = await ml_model_service.list(
            session,
            is_active=True,
            model_type=MLModelType.IMAGE_GENERATION,
            limit=1,
            offset=0,
        )
        if not models:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active image generation model configured",
            )
        ml_model = models[0]

    cost = ml_model.cost_credits or 0

    # 2. Быстрая проверка баланса перед постановкой задачи
    if cost > 0:
        db_user = await user_service.get(session, current_user.id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if db_user.balance_credits < cost:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not enough credits on balance",
            )

    # 3. Ставим задачу в Celery
    try:
        task_id = enqueue_image_generation(
            user_id=current_user.id,
            prompt_ru=payload.prompt,
            credits_spent=cost,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to enqueue prediction task", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue prediction task",
        ) from exc

    # 4. Возвращаем информацию о постановке задачи
    return PredictionEnqueueResponse(
        task_id=str(task_id),
        queued=True,
        cost_credits=cost,
        message=(
            "Prediction task enqueued. "
            "Result will appear in your predictions history "
            "after processing is finished."
        ),
    )

@router.get(
    "",
    response_model=List[PredictionOut],
)
async def list_my_predictions(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[PredictionOut]:
    """
    История prediction-запросов текущего пользователя.
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
async def get_prediction(
    prediction_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PredictionOut:
    """
    Получить конкретный prediction текущего пользователя.
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
    Вспомогательный эндпоинт для получения изображения по prediction_id.

    - Проверяет, что prediction существует и принадлежит текущему пользователю;
    - Если записи нет — 404;
    - Строит presigned URL по s3_key и делает редирект на него.

    Сам бакет остаётся приватным, доступ только по временной ссылке.
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

    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@router.get(
    "/demo/{task_id}",
    response_model=PredictionOut,
)
async def get_demo_prediction(
    task_id: str,
    session: AsyncSession = Depends(get_db),
) -> PredictionOut:
    """
    Публичный эндпоинт: отдаёт демо-prediction по task_id,
    но только если он принадлежит DEMO-пользователю.
    """
    demo_email = settings.demo_email
    if not demo_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo user not configured",
        )

    demo_user = await user_service.get_by_email(session, demo_email)
    if not demo_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo user not configured",
        )

    prediction = await prediction_service.get_by_task_id(session, task_id)
    if not prediction or prediction.user_id != demo_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo prediction not found",
        )

    return prediction


@router.post(
    "/demo/claim",
    response_model=MessageResponse,
)
async def claim_demo_prediction(
    body: DemoClaimRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Привязать демо-предсказание к текущему пользователю:
    создаёт копию PredictionRequest с credits_spent=0.
    """
    cloned = await prediction_service.clone_demo_prediction_for_user(
        session=session,
        task_id=body.task_id,
        new_user=current_user,
    )
    if not cloned:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo prediction not found",
        )

    await session.commit()

    return MessageResponse(message="Демо-предсказание добавлено в вашу историю")