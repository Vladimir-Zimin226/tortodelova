from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    """
    Простые настройки проекта, читаются из переменных окружения.

    Важно:
    - DB_URL должен быть async-URL для SQLAlchemy, например:
      postgresql+asyncpg://postgres:postgres@db:5432/tortodelova
    - SEED_* и PASSWORD_SALT являются обязательными и
      должны быть заданы в окружении (app.env / docker-compose).
    """

    def __init__(self) -> None:
        # URL для подключения к БД (asyncpg)
        self.db_url: str = os.getenv(
            "DB_URL",
            "postgresql+asyncpg://postgres:postgres@db:5432/tortodelova",
        )

        # Включить SQL echo (логирование SQL-запросов)
        self.db_echo: bool = os.getenv("DB_ECHO", "false").lower() == "true"

        # Сидинг пользователей — строго обязательные переменные
        self.seed_admin_email: str = self._get_required_env("SEED_ADMIN_EMAIL")
        self.seed_admin_password: str = self._get_required_env("SEED_ADMIN_PASSWORD")

        self.seed_user_email: str = self._get_required_env("SEED_USER_EMAIL")
        self.seed_user_password: str = self._get_required_env("SEED_USER_PASSWORD")

        # Соль для хеширования паролей — тоже обязательна
        self.password_salt: str = self._get_required_env("PASSWORD_SALT")

    @staticmethod
    def _get_required_env(name: str) -> str:
        """
        Возвращает значение обязательной переменной окружения.

        Если переменная не задана или пуста, кидает RuntimeError,
        из-за чего приложение упадёт при старте с понятным сообщением.
        """
        value = os.getenv(name)
        if value is None or value.strip() == "":
            raise RuntimeError(
                f"Обязательная переменная окружения {name} не задана "
                f"или пуста. Укажите её в app.env / docker-compose."
            )
        return value


@lru_cache
def get_settings() -> Settings:
    """
    Кешированный доступ к настройкам, чтобы не пересоздавать объект.
    """
    return Settings()
