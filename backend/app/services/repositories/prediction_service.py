import logging
from typing import Optional, Sequence, Any

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.prediction import PredictionRequest, PredictionStatus
from app.models.user import User
from app.services.repositories.user_service import user_service
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)
settings = get_settings()


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

    async def list_all(
        self,
        session: AsyncSession,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[PredictionRequest]:
        """
        Список всех prediction-запросов (для админки).
        """
        res = await session.execute(
            select(PredictionRequest)
            .order_by(PredictionRequest.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = res.scalars().all()

        logger.info(
            "PredictionService.list_all: returned=%s (offset=%s, limit=%s)",
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

    async def get_by_task_id(
        self,
        session: AsyncSession,
        task_id: str,
    ) -> Optional[PredictionRequest]:
        res = await session.execute(
            select(PredictionRequest).where(
                PredictionRequest.celery_task_id == task_id
            )
        )
        prediction = res.scalars().first()

        logger.info(
            "PredictionService.get_by_task_id: task_id=%s found=%s",
            task_id,
            bool(prediction),
        )
        return prediction

    async def clone_demo_prediction_for_user(
        self,
        session: AsyncSession,
        *,
        task_id: str,
        new_user: User,
    ) -> Optional[PredictionRequest]:
        """
        Находит демо-предсказание по task_id у DEMO-пользователя
        и создаёт его копию для new_user с credits_spent = 0
        и НОВЫМИ (s3_key, public_url), указывающими на реальную копию объекта в S3.
        """
        demo_email = settings.demo_email
        if not demo_email:
            logger.warning("clone_demo_prediction_for_user: DEMO_EMAIL not configured")
            return None

        demo_user = await user_service.get_by_email(session, demo_email)
        if not demo_user:
            logger.warning("clone_demo_prediction_for_user: demo user not found")
            return None

        src = await self.get_by_task_id(session, task_id)
        if not src or src.user_id != demo_user.id:
            logger.info(
                "clone_demo_prediction_for_user: prediction not found or not demo (task_id=%s)",
                task_id,
            )
            return None

        # Клонируем объект в S3 под новым ключом для нового пользователя
        new_s3_key, new_public_url = await storage_service.clone_prediction_image(
            source_s3_key=src.s3_key,
            target_user_id=new_user.id,
        )

        cloned = await self.create(
            session=session,
            user_id=new_user.id,
            prompt_ru=src.prompt_ru,
            prompt_en=src.prompt_en or "",
            s3_key=new_s3_key,
            public_url=new_public_url,
            credits_spent=0,  # для нового пользователя это бесплатная генерация
            status=src.status or PredictionStatus.SUCCESS,
            celery_task_id=None,  # у копии task_id можно не хранить
        )

        logger.info(
            "clone_demo_prediction_for_user: task_id=%s cloned_to_user=%s new_prediction_id=%s",
            task_id,
            new_user.id,
            cloned.id,
        )
        return cloned


prediction_service = PredictionService()
