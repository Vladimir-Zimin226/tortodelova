from __future__ import annotations

import logging
from typing import Optional, Sequence, Any

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction import PredictionRequest

logger = logging.getLogger(__name__)


class PredictionService:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        prompt_ru: str,
        prompt_en: str,
        s3_key: str,
        public_url: str,
        credits_spent: int,
        **extra_fields: Any,
    ) -> PredictionRequest:
        """
        Создать запись предикшена.
        status и created_at можно оставить на дефолты модели.
        """
        prediction = PredictionRequest(
            user_id=user_id,
            prompt_ru=prompt_ru,
            prompt_en=prompt_en,
            s3_key=s3_key,
            public_url=public_url,
            credits_spent=credits_spent,
            **extra_fields,
        )
        session.add(prediction)
        await session.flush()
        await session.refresh(prediction)

        logger.info(
            "PredictionService.create: id=%s user_id=%s credits_spent=%s s3_key=%s",
            prediction.id,
            prediction.user_id,
            prediction.credits_spent,
            prediction.s3_key,
        )
        return prediction

    async def get(
        self,
        session: AsyncSession,
        prediction_id: int,
    ) -> Optional[PredictionRequest]:
        prediction = await session.get(PredictionRequest, prediction_id)
        logger.info(
            "PredictionService.get: id=%s found=%s",
            prediction_id,
            bool(prediction),
        )
        return prediction

    async def list_by_user(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[PredictionRequest]:
        res = await session.execute(
            select(PredictionRequest)
            .where(PredictionRequest.user_id == user_id)
            .order_by(PredictionRequest.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = res.scalars().all()
        logger.info(
            "PredictionService.list_by_user: user_id=%s returned=%s "
            "(offset=%s, limit=%s)",
            user_id,
            len(items),
            offset,
            limit,
        )
        return items

    async def update(
        self,
        session: AsyncSession,
        prediction_id: int,
        **fields,
    ) -> Optional[PredictionRequest]:
        if not fields:
            logger.info(
                "PredictionService.update: no fields to update (id=%s)",
                prediction_id,
            )
            return await self.get(session, prediction_id)

        await session.execute(
            update(PredictionRequest)
            .where(PredictionRequest.id == prediction_id)
            .values(**fields)
        )
        await session.flush()

        prediction = await self.get(session, prediction_id)
        logger.info(
            "PredictionService.update: id=%s updated_with=%s exists=%s",
            prediction_id,
            fields,
            bool(prediction),
        )
        return prediction

    async def delete(self, session: AsyncSession, prediction_id: int) -> bool:
        res = await session.execute(
            delete(PredictionRequest).where(PredictionRequest.id == prediction_id)
        )
        await session.flush()

        deleted = res.rowcount or 0
        logger.info(
            "PredictionService.delete: id=%s deleted=%s",
            prediction_id,
            bool(deleted),
        )
        return bool(deleted)


prediction_service = PredictionService()
