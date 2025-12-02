from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.transaction import Transaction
    from app.models.prediction import PredictionRequest


class UserRole(str, enum.Enum):
    """
    Роль пользователя в системе.

    USER  — обычный пользователь, может тратить кредиты и создавать запросы.
    ADMIN — администратор, может пополнять балансы и видеть админские разделы.
    """
    USER = "user"
    ADMIN = "admin"


class User(Base):
    """
    Пользователь ML-сервиса.

    Таблица `users` отвечает только за хранение данных пользователя:

    - аутентификация (email + hashed_password);
    - авторизация (role);
    - текущий баланс кредитов (balance_credits);
    - связи с транзакциями и prediction-запросами.

    Бизнес-логика управления балансом (пополнения/списания, проверки
    достаточности средств и создание Transaction) вынесена в сервисный
    слой (например, UserService / UserBalanceService), чтобы не
    перегружать модель.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        index=True,
        nullable=False,
        doc="Уникальный email пользователя.",
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Хеш пароля (никогда не хранить открытый пароль).",
    )

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.USER,
        doc="Роль пользователя в системе.",
    )

    balance_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Текущий баланс кредитов пользователя (целое число, >= 0).",
    )

    # --- Связи ---

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="Финансовые транзакции пользователя (пополнения/списания).",
    )

    prediction_requests: Mapped[list["PredictionRequest"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="Запросы на генерацию изображений.",
    )

    # --- Фабрика создания с минимальной валидацией ---

    @classmethod
    def create(
        cls,
        email: str,
        hashed_password: str,
        role: UserRole = UserRole.USER,
        balance_credits: int = 0,
    ) -> "User":
        """
        Создаёт нового пользователя с базовой валидацией входных данных.

        Валидация здесь ограничена инвариантами самой сущности:
        - корректность email;
        - непустой хеш пароля;
        - неотрицательный начальный баланс.

        Остальная бизнес-логика выполняется в сервисном слое.
        """
        normalized_email = cls._normalize_email(email)
        cls._validate_email(normalized_email)
        cls._validate_hashed_password(hashed_password)
        cls._validate_non_negative_balance(balance_credits)

        return cls(
            email=normalized_email,
            hashed_password=hashed_password,
            role=role,
            balance_credits=balance_credits,
        )

    # --- Приватные методы валидации / нормализации ---

    @staticmethod
    def _normalize_email(email: str) -> str:
        """Приводит email к каноничному виду (обрезка пробелов, lower-case)."""
        return email.strip().lower()

    @staticmethod
    def _validate_email(email: str) -> None:
        """Минимальная валидация email."""
        if not email:
            raise ValueError("Email не может быть пустым.")
        if "@" not in email or "." not in email:
            raise ValueError(f"Некорректный email: {email!r}.")

    @staticmethod
    def _validate_hashed_password(hashed_password: str) -> None:
        """
        Проверяет, что хеш пароля не пустой.

        Само хеширование выполняется в слое security (core/security.py).
        """
        if not hashed_password:
            raise ValueError("Хеш пароля не может быть пустым.")

    @staticmethod
    def _validate_non_negative_balance(balance: int) -> None:
        """Гарантирует, что начальный баланс кредитов не отрицательный."""
        if balance < 0:
            raise ValueError("Начальный баланс кредитов не может быть отрицательным.")

    def __repr__(self) -> str:
        return (
            f"User(id={self.id!r}, email={self.email!r}, "
            f"role={self.role!r}, balance_credits={self.balance_credits!r})"
        )
