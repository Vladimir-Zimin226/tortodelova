from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .transaction import Transaction
    from .prediction import PredictionRequest


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

    Хранится в таблице `users`. Отвечает за:

    - аутентификацию (email + hashed_password);
    - авторизацию (role);
    - текущий баланс кредитов;
    - связь с транзакциями и запросами на генерацию.

    Помимо полей БД, содержит методы предметной области:
    - создание пользователя с валидацией (`create`);
    - операции с балансом (`add_credits`, `spend_credits`, `can_spend`).
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

    # --- Фабричные методы / бизнес-логика ---

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

        Используется вместо прямого вызова конструктора в бизнес-логике,
        чтобы не дублировать проверки.

        :raises ValueError: если email/пароль некорректны или баланс отрицательный.
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

    def can_spend(self, credits: int) -> bool:
        """
        Проверяет, достаточно ли у пользователя кредитов для списания.

        :param credits: требуемое число кредитов (> 0)
        :return: True, если баланс достаточный; иначе False.
        """
        self._validate_positive_credits_value(credits)
        return self.balance_credits >= credits

    def spend_credits(self, credits: int) -> None:
        """
        Списывает кредиты с баланса пользователя.

        Валидация:
        - credits > 0
        - у пользователя достаточно средств

        :raises ValueError: если сумма некорректна или недостаточно средств.
        """
        self._validate_positive_credits_value(credits)

        if not self.can_spend(credits):
            raise ValueError(
                f"Недостаточно кредитов: запрошено {credits}, "
                f"доступно {self.balance_credits}."
            )

        self.balance_credits -= credits

    def add_credits(self, credits: int) -> None:
        """
        Пополняет баланс пользователя на заданное количество кредитов.

        :param credits: сколько кредитов добавить (> 0)
        :raises ValueError: если credits <= 0.
        """
        self._validate_positive_credits_value(credits)
        self.balance_credits += credits

    # --- Приватные методы валидации / нормализации ---

    @staticmethod
    def _normalize_email(email: str) -> str:
        """
        Приводит email к каноничному виду (обрезка пробелов, lower-case).
        """
        return email.strip().lower()

    @staticmethod
    def _validate_email(email: str) -> None:
        """
        Минимальная валидация email.

        Здесь осознанно не используется сложная проверка по RFC,
        достаточно базовой для нашего кейса.
        """
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
        """
        Гарантирует, что баланс кредитов не отрицательный.
        """
        if balance < 0:
            raise ValueError("Начальный баланс кредитов не может быть отрицательным.")

    @staticmethod
    def _validate_positive_credits_value(credits: int) -> None:
        """
        Проверяет, что значение кредитов больше нуля.
        """
        if credits <= 0:
            raise ValueError("Количество кредитов должно быть > 0.")

    def __repr__(self) -> str:
        return (
            f"User(id={self.id!r}, email={self.email!r}, "
            f"role={self.role!r}, balance_credits={self.balance_credits!r})"
        )
