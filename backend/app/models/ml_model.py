from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Integer,
    String,
    Boolean,
    DateTime,
    Enum as SAEnum,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MLModelType(str, enum.Enum):
    """
    Тип ML-модели.

    Используется для разграничения логики в MlService:
    - translation        — модели перевода текста;
    - image_generation   — модели генерации изображений.
    """

    TRANSLATION = "translation"
    IMAGE_GENERATION = "image_generation"


class MLModel(Base):
    """
    Конфигурация ML-модели, доступной в системе.

    Таблица `ml_models` описывает *какие* модели у нас есть и как
    они используются:
    - системное имя и заголовок;
    - тип (перевод / генерация изображений);
    - информация о движке/версии;
    - стоимость запроса в кредитах;
    - флаг активности.

    На уровне Python-кода к этой сущности будет обращаться MlService,
    чтобы понять:
    - какую конкретно модель использовать;
    - сколько кредитов должна стоить операция.
    """

    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        doc="Уникальный идентификатор ML-модели.",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        doc=(
            "Системное имя модели, например "
            "'Helsinki-NLP/opus-mt-ru-en' или 'dreamshaper_v8'."
        ),
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Человекочитаемое название модели для UI.",
    )

    model_type: Mapped[MLModelType] = mapped_column(
        SAEnum(MLModelType, name="ml_model_type"),
        nullable=False,
        doc="Тип модели (перевод текста / генерация изображений).",
    )

    engine: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc=(
            "Движок / провайдер модели, например 'huggingface', "
            "'diffusers', 'onnx' и т.п."
        ),
    )

    version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Версия модели, если применимо (например, 'v8', '1.5').",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Признак того, что модель доступна для использования.",
    )

    cost_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Стоимость одного запроса к модели в кредитах (>= 0).",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Момент регистрации модели в системе.",
    )

    # --- Фабричный метод ---

    @classmethod
    def create(
        cls,
        name: str,
        display_name: str,
        model_type: MLModelType,
        engine: str,
        version: str | None = None,
        cost_credits: int = 0,
        is_active: bool = True,
    ) -> "MLModel":
        """
        Создаёт новую запись ML-модели с базовой валидацией.

        Валидация ограничена инвариантами самой сущности:
        - непустые name / display_name / engine;
        - cost_credits >= 0.
        """
        normalized_name = name.strip()
        normalized_display_name = display_name.strip()
        normalized_engine = engine.strip()

        cls._validate_name(normalized_name)
        cls._validate_display_name(normalized_display_name)
        cls._validate_engine(normalized_engine)
        cls._validate_cost_non_negative(cost_credits)

        return cls(
            name=normalized_name,
            display_name=normalized_display_name,
            model_type=model_type,
            engine=normalized_engine,
            version=version,
            cost_credits=cost_credits,
            is_active=is_active,
        )

    # --- Приватные валидаторы ---

    @staticmethod
    def _validate_name(name: str) -> None:
        if not name:
            raise ValueError("Имя ML-модели не может быть пустым.")

    @staticmethod
    def _validate_display_name(display_name: str) -> None:
        if not display_name:
            raise ValueError(
                "Отображаемое название ML-модели не может быть пустым."
            )

    @staticmethod
    def _validate_engine(engine: str) -> None:
        if not engine:
            raise ValueError("Поле 'engine' для ML-модели не может быть пустым.")

    @staticmethod
    def _validate_cost_non_negative(cost_credits: int) -> None:
        if cost_credits < 0:
            raise ValueError(
                "Стоимость запроса к ML-модели (cost_credits) не может быть отрицательной."
            )

    def __repr__(self) -> str:
        return (
            f"MLModel(id={self.id!r}, name={self.name!r}, "
            f"type={self.model_type!r}, cost_credits={self.cost_credits!r})"
        )