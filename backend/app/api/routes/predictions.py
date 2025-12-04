from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, constr, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User
from app.models.transaction import TransactionType
from app.models.ml_model import MLModelType
from app.services.repositories.user_service import user_service
from app.services.repositories.prediction_service import prediction_service
from app.services.repositories.ml_model_service import ml_model_service
from app.api.routes.auth import get_current_user

router = APIRouter(
    prefix="/api/predictions",
    tags=["predictions"],
)

S3_PUBLIC_ENDPOINT = os.getenv("S3_PUBLIC_ENDPOINT", "").rstrip("/")
S3_BUCKET = os.getenv("S3_BUCKET", "").strip("/")


class PredictionCreateRequest(BaseModel):
    prompt: constr(min_length=1)
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


def _build_public_s3_path(s3_key: str) -> str:
    """
    Формирование публичного URL для объекта в S3/MinIO.

    Если env-переменные не заданы, возвращаем просто s3_key,
    чтобы интерфейс всё равно работал.
    """
    if S3_PUBLIC_ENDPOINT and S3_BUCKET:
        return f"{S3_PUBLIC_ENDPOINT}/{S3_BUCKET}/{s3_key}"
    return s3_key


@router.post(
    "",
    response_model=PredictionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_prediction(
    payload: PredictionCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PredictionOut:
    """
    Отправка данных для предсказания / генерации изображения:

    - выбираем активную модель генерации изображений;
    - перед запуском тяжёлых операций проверяем, хватает ли кредитов;
    - создаём запись PredictionRequest со статусом 'success';
    - списываем кредиты по стоимости ML-модели (cost_credits).

    Позже сюда встроим реальные вызовы ml_service + storage_service.
    """
    # 1. Выбираем ML-модель
    if payload.model_id is not None:
        ml_model = await ml_model_service.get(session, payload.model_id)
        if not ml_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ML model not found",
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

    # Быстрая проверка баланса перед "дорогими" операциями
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

    # 2. Упрощённый “перевод”
    prompt_ru = payload.prompt
    prompt_en = payload.prompt  # здесь позже можно вызвать реальный RU->EN

    # 3. Формируем s3_key / public_url (без фактической загрузки файла)
    s3_key = f"user_{current_user.id}/prediction_{uuid4().hex}.png"
    public_url = _build_public_s3_path(s3_key)

    # 4. DB-транзакция: создаём prediction + списываем кредиты
    try:
        prediction = await prediction_service.create(
            session,
            user_id=current_user.id,
            prompt_ru=prompt_ru,
            prompt_en=prompt_en,
            s3_key=s3_key,
            public_url=public_url,
            credits_spent=cost,
            status="success",
        )

        if cost > 0:
            # списываем кредиты только после успешного создания prediction
            await user_service.change_balance_with_transaction(
                session,
                user_id=current_user.id,
                amount=cost,
                tx_type=TransactionType.DEBIT,
                description=f"Image generation (model={ml_model.name})",
            )

        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        await session.rollback()
        raise

    return prediction

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
