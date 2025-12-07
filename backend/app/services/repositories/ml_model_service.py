from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ml_model import MLModel, MLModelType

logger = logging.getLogger(__name__)


class MLModelService:
    """
    Сервис-репозиторий для работы с таблицей ml_models.

    Описывает полный CRUD и типичные операции выборки:
    - поиск по id и name;
    - фильтрация по типу и активности.
    """

    async def create(
        self,
        session: AsyncSession,
        *,
        name: str,
        display_name: str,
        model_type: MLModelType,
        engine: str,
        version: str | None = None,
        cost_credits: int = 0,
        is_active: bool = True,
    ) -> MLModel:
        """
        Создать новую ML-модель.

        Валидация инвариантов сущности выполняется в MLModel.create().
        """
        model = MLModel.create(
            name=name,
            display_name=display_name,
            model_type=model_type,
            engine=engine,
            version=version,
            cost_credits=cost_credits,
            is_active=is_active,
        )
        session.add(model)
        await session.flush()
        await session.refresh(model)

        logger.info(
            "MLModelService.create: id=%s name=%s type=%s cost=%s active=%s",
            model.id,
            model.name,
            model.model_type,
            model.cost_credits,
            model.is_active,
        )
        return model

    async def get(
        self,
        session: AsyncSession,
        model_id: int,
    ) -> Optional[MLModel]:
        """Получить ML-модель по id."""
        model = await session.get(MLModel, model_id)
        logger.info(
            "MLModelService.get: id=%s found=%s",
            model_id,
            bool(model),
        )
        return model

    async def get_by_name(
        self,
        session: AsyncSession,
        name: str,
    ) -> Optional[MLModel]:
        """Получить ML-модель по системному имени (name)."""
        res = await session.execute(
            select(MLModel).where(MLModel.name == name)
        )
        model = res.scalar_one_or_none()
        logger.info(
            "MLModelService.get_by_name: name=%s found=%s",
            name,
            bool(model),
        )
        return model

    async def list(
        self,
        session: AsyncSession,
        *,
        is_active: Optional[bool] = None,
        model_type: Optional[MLModelType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[MLModel]:
        """
        Список ML-моделей с возможностью фильтрации по активности и типу.
        """
        query = select(MLModel)

        if is_active is not None:
            query = query.where(MLModel.is_active == is_active)

        if model_type is not None:
            query = query.where(MLModel.model_type == model_type)

        query = query.order_by(MLModel.id).offset(offset).limit(limit)

        res = await session.execute(query)
        models = res.scalars().all()

        logger.info(
            "MLModelService.list: returned=%s (offset=%s, limit=%s, "
            "is_active=%s, model_type=%s)",
            len(models),
            offset,
            limit,
            is_active,
            model_type,
        )
        return models

    async def get_first_active_by_type(
        self,
        session: AsyncSession,
        model_type: MLModelType,
    ) -> Optional[MLModel]:
        """
        Вернуть первую активную модель указанного типа (например, image_generation).
        """
        res = await session.execute(
            select(MLModel)
            .where(
                MLModel.model_type == model_type,
                MLModel.is_active.is_(True),
            )
            .order_by(MLModel.id)
        )
        model = res.scalar_one_or_none()
        logger.info(
            "MLModelService.get_first_active_by_type: type=%s found=%s",
            model_type,
            bool(model),
        )
        return model

    async def update(
        self,
        session: AsyncSession,
        model_id: int,
        **fields,
    ) -> Optional[MLModel]:
        """
        Обновить поля ML-модели (например, cost_credits, is_active и т.п.).
        """
        if not fields:
            logger.info(
                "MLModelService.update: no fields to update (id=%s)",
                model_id,
            )
            return await self.get(session, model_id)

        await session.execute(
            update(MLModel)
            .where(MLModel.id == model_id)
            .values(**fields)
        )
        await session.flush()

        model = await self.get(session, model_id)
        logger.info(
            "MLModelService.update: id=%s updated_with=%s exists=%s",
            model_id,
            fields,
            bool(model),
        )
        return model

    async def delete(
        self,
        session: AsyncSession,
        model_id: int,
    ) -> bool:
        """Удалить ML-модель по id."""
        res = await session.execute(
            delete(MLModel).where(MLModel.id == model_id)
        )
        await session.flush()

        deleted = res.rowcount or 0
        logger.info(
            "MLModelService.delete: id=%s deleted=%s",
            model_id,
            bool(deleted),
        )
        return bool(deleted)


ml_model_service = MLModelService()
