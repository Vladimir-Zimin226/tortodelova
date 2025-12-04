from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from .user import User


class TransactionType(str, enum.Enum):
    """
    Тип транзакции по балансу пользователя.

    DEBIT  — списание кредитов;
    CREDIT — пополнение кредитов.
    """
    DEBIT = "debit"
    CREDIT = "credit"


class Transaction(Base):
    """
    Финансовая транзакция пользователя.

    Хранится в таблице `transactions` и отражает изменение баланса кредитов.
    Важные моменты:

    - amount всегда строго положительный (> 0);
    - type определяет направление (списание/пополнение);
    - описание (description) используется для аудита (комментарий, источник оплаты).

    В доменной логике создаётся через фабричные методы:
    - create_debit / create_credit / create
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Идентификатор пользователя, к которому относится транзакция.",
    )

    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Количество кредитов (целое число, > 0).",
    )

    type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType, name="transaction_type"),
        nullable=False,
        doc="Тип транзакции: списание (debit) или пополнение (credit).",
    )

    description: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        doc="Произвольный комментарий к транзакции (источник, причина и т.п.).",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Момент создания транзакции.",
    )

    # --- Связи ---

    user: Mapped["User"] = relationship(
        back_populates="transactions",
        lazy="joined",
        doc="Пользователь, к которому относится транзакция.",
    )

    # --- Фабричные методы / бизнес-логика ---

    @classmethod
    def create(
        cls,
        user_id: int,
        amount: int,
        tx_type: TransactionType,
        description: str | None = None,
    ) -> "Transaction":
        """
        Создаёт транзакцию с базовой валидацией суммы.

        :param user_id: идентификатор пользователя
        :param amount: количество кредитов (> 0)
        :param tx_type: тип транзакции (DEBIT / CREDIT)
        :param description: комментарий к транзакции
        :raises ValueError: если amount <= 0
        """
        cls._validate_amount_positive(amount)

        return cls(
            user_id=user_id,
            amount=amount,
            type=tx_type,
            description=description,
        )

    @classmethod
    def create_debit(
        cls,
        user_id: int,
        amount: int,
        description: str | None = None,
    ) -> "Transaction":
        """
        Создаёт транзакцию списания кредитов (DEBIT).
        """
        return cls.create(
            user_id=user_id,
            amount=amount,
            tx_type=TransactionType.DEBIT,
            description=description,
        )

    @classmethod
    def create_credit(
        cls,
        user_id: int,
        amount: int,
        description: str | None = None,
    ) -> "Transaction":
        """
        Создаёт транзакцию пополнения кредитов (CREDIT).
        """
        return cls.create(
            user_id=user_id,
            amount=amount,
            tx_type=TransactionType.CREDIT,
            description=description,
        )

    # --- Удобные геттеры-свойства ---

    @property
    def is_debit(self) -> bool:
        """True, если это списание кредитов."""
        return self.type == TransactionType.DEBIT

    @property
    def is_credit(self) -> bool:
        """True, если это пополнение кредитов."""
        return self.type == TransactionType.CREDIT

    # --- Приватная валидация ---

    @staticmethod
    def _validate_amount_positive(amount: int) -> None:
        """
        Гарантирует, что сумма транзакции строго положительна.
        """
        if amount <= 0:
            raise ValueError("Сумма транзакции должна быть > 0.")

    def __repr__(self) -> str:
        return (
            f"Transaction(id={self.id!r}, user_id={self.user_id!r}, "
            f"amount={self.amount!r}, type={self.type!r})"
        )
