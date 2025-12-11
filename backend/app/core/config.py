from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    """
    Простые настройки проекта, читаются из переменных окружения.

    Важно:
    - DB_URL должен быть async-URL для SQLAlchemy, например:
      postgresql+asyncpg://postgres:postgres@db:5432/tortodelova
    - SEED_* являются обязательными и должны быть заданы
      в окружении (app.env / docker-compose).
    """

    def __init__(self) -> None:
        self.db_url: str = os.getenv(
            "DB_URL",
            "postgresql+asyncpg://postgres:postgres@database:5432/tortodelova",
        )

        # Включить SQL echo (логирование SQL-запросов)
        self.db_echo: bool = os.getenv("DB_ECHO", "false").lower() == "true"

        # Сидинг пользователей — строго обязательные переменные
        self.seed_admin_email: str = self._get_required_env("SEED_ADMIN_EMAIL")
        self.seed_admin_password: str = self._get_required_env("SEED_ADMIN_PASSWORD")

        self.seed_user_email: str = self._get_required_env("SEED_USER_EMAIL")
        self.seed_user_password: str = self._get_required_env("SEED_USER_PASSWORD")

        # Демо-пользователь (опционально)
        # Используется для первой бесплатной генерации от имени DEMO-аккаунта.
        self.demo_email: str | None = os.getenv("DEMO_EMAIL") or None
        self.demo_password: str | None = os.getenv("DEMO_PASSWORD") or None

        # === JWT ===
        # Секрет для подписи JWT — обязателен, отдельно от паролей.
        self.jwt_secret_key: str = self._get_required_env("JWT_SECRET_KEY")
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes: int = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )

        # Celery / RabbitMQ
        # По умолчанию — стандартный guest/guest на сервисе rabbitmq из docker-compose.
        self.celery_broker_url: str = os.getenv(
            "CELERY_BROKER_URL",
            "amqp://guest:guest@rabbitmq:5672//",
        )
        self.celery_result_backend: str = os.getenv(
            "CELERY_RESULT_BACKEND",
            "rpc://",
        )

        # --- S3 / MinIO ---
        # Внутренний endpoint, на который будет ходить бэкенд (через docker-сеть).
        self.s3_endpoint: str = os.getenv(
            "S3_ENDPOINT",
            "http://minio:9000",
        )

        # Регион (для MinIO можно указать любой)
        self.s3_region: str = os.getenv("S3_REGION", "ru-7")

        # Имя бакета — обязательно
        self.s3_bucket: str = self._get_required_env("S3_BUCKET")

        # Ключи доступа к MinIO/S3 — тоже обязательно
        self.s3_access_key: str = self._get_required_env("S3_ACCESS_KEY")
        self.s3_secret_key: str = self._get_required_env("S3_SECRET_KEY")

        # Публичный endpoint, который будем отдавать наружу (браузеру, клиентам и т.п.).
        self.s3_public_endpoint: str = os.getenv(
            "S3_PUBLIC_ENDPOINT",
            self.s3_endpoint,
        )

        # Стиль адресации (path / virtual).
        self.s3_addressing_style: str = os.getenv("S3_ADDRESSING_STYLE", "path")

        # === ML-модели ===
        # Общая директория
        self.ml_models_dir: str = os.getenv("ML_MODELS_DIR", "/models")

        # Конкретные папки
        self.translator_model_dir: str = os.getenv(
            "TRANSLATOR_MODEL_DIR",
            os.path.join(self.ml_models_dir, "translator", "opus-mt-ru-en"),
        )
        self.dreamshaper_model_dir: str = os.getenv(
            "DREAMSHAPER_MODEL_DIR",
            os.path.join(self.ml_models_dir, "dreamshaper-8"),
        )

        # На локальной машине используем CPU.
        # Если потом будет GPU — поставить TORCH_DEVICE=cuda.
        self.torch_device: str = os.getenv("TORCH_DEVICE", "cpu")

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