from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Integer,
    String,
    Text,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from .user import User


class PredictionStatus(str, enum.Enum):
    """
    Статус запроса на генерацию изображения.

    PENDING — запрос создан, генерация в процессе.
    SUCCESS — изображение успешно сгенерировано и сохранено в S3.
    FAILED  — при генерации или сохранении произошла ошибка.
    """
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class PredictionRequest(Base):
    """
    Запрос пользователя на генерацию изображения.

    Хранится в таблице `prediction_requests`. Логика процесса:

    1. Пользователь отправляет промпт на русском (`prompt_ru`).
    2. Мы переводим его в английский (`prompt_en`) через модель перевода.
    3. По английскому промпту запускается генерация через DreamShaper.
    4. Результат (изображение) сохраняется в S3/MinIO по `s3_key`.
    5. Формируется публичный URL (`public_url`) вида:
       {S3_PUBLIC_ENDPOINT}/{S3_BUCKET}/{s3_key}
    6. В `credits_spent` фиксируется число списанных кредитов.
    7. `status` становится SUCCESS после успешной генерации и сохранения.

    Кредиты списываются только после успешной загрузки в MinIO — это
    будет обеспечиваться в сервисном слое транзакцией БД.
    """

    __tablename__ = "prediction_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Идентификатор пользователя, создавшего запрос.",
    )

    prompt_ru: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Исходный промпт на русском языке.",
    )

    prompt_en: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Промпт, переведённый на английский (может быть NULL до перевода).",
    )

    s3_key: Mapped[str] = mapped_column(
        String(512),
        unique=True,
        nullable=False,
        doc="Ключ объекта в S3/MinIO.",
    )

    public_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        doc="Публичный URL изображения, основанный на S3_PUBLIC_ENDPOINT.",
    )

    credits_spent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Сколько кредитов списано за эту генерацию.",
    )

    status: Mapped[PredictionStatus] = mapped_column(
        SAEnum(PredictionStatus, name="prediction_status"),
        nullable=False,
        default=PredictionStatus.PENDING,
        doc="Текущий статус запроса.",
    )

    celery_task_id: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
        index=True,
        doc="ID Celery-задачи генерации (для демо-сценариев).",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Момент создания записи.",
    )

    # --- Связи ---

    user: Mapped["User"] = relationship(
        back_populates="prediction_requests",
        lazy="joined",
        doc="Пользователь, создавший запрос.",
    )

    # --- Фабричные методы / бизнес-логика ---

    @classmethod
    def create_success(
        cls,
        user_id: int,
        prompt_ru: str,
        prompt_en: str,
        s3_key: str,
        public_url: str,
        credits_spent: int,
    ) -> "PredictionRequest":
        """
        Создаёт запись об успешно выполненной генерации.

        Предполагается, что на момент вызова:
        - перевод уже выполнен;
        - изображение уже сохранено в S3/MinIO;
        - `s3_key` и `public_url` известны;
        - операция выполняется в рамках транзакции, где также списываются кредиты.

        :raises ValueError: если строки пустые или credits_spent < 0.
        """
        cls._validate_non_empty("prompt_ru", prompt_ru)
        cls._validate_non_empty("prompt_en", prompt_en)
        cls._validate_non_empty("s3_key", s3_key)
        cls._validate_non_empty("public_url", public_url)
        cls._validate_non_negative_credits(credits_spent)

        return cls(
            user_id=user_id,
            prompt_ru=prompt_ru,
            prompt_en=prompt_en,
            s3_key=s3_key,
            public_url=public_url,
            credits_spent=credits_spent,
            status=PredictionStatus.SUCCESS,
        )

    def mark_failed(self) -> None:
        """
        Помечает запрос как проваленный.

        Может использоваться, если на этапе генерации или сохранения
        произошла ошибка и мы хотим зафиксировать факт неуспешной попытки.
        """
        self.status = PredictionStatus.FAILED

    def mark_pending(self) -> None:
        """
        Помечает запрос как ожидающий (PENDING).

        Полезно, если мы хотим создать запись заранее и позже обновить её
        до SUCCESS/FAILED. Сейчас основная логика создаёт SUCCESS после
        завершения генерации, но метод оставлен для гибкости.
        """
        self.status = PredictionStatus.PENDING

    # --- Приватные методы валидации ---

    @staticmethod
    def _validate_non_empty(field_name: str, value: str) -> None:
        """
        Проверяет, что строковое поле не пустое.
        """
        if not value or not value.strip():
            raise ValueError(f"Поле {field_name!r} не может быть пустым.")

    @staticmethod
    def _validate_non_negative_credits(credits: int) -> None:
        """
        Проверяет, что число списанных кредитов не отрицательно.

        Норма: 0 (если списаний не было) или больше.
        """
        if credits < 0:
            raise ValueError("Количество списанных кредитов не может быть отрицательным.")

    def __repr__(self) -> str:
        return (
            f"PredictionRequest(id={self.id!r}, user_id={self.user_id!r}, "
            f"status={self.status!r}, s3_key={self.s3_key!r})"
        )