import os
import sys
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[2]  # .../backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("SEED_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "adminpass123")
os.environ.setdefault("SEED_USER_EMAIL", "user@example.com")
os.environ.setdefault("SEED_USER_PASSWORD", "userpass123")

os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("S3_ACCESS_KEY", "test-access")
os.environ.setdefault("S3_SECRET_KEY", "test-secret")
os.environ.setdefault("S3_ENDPOINT", "http://minio:9000")
os.environ.setdefault("S3_PUBLIC_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("S3_REGION", "us-east-1")
os.environ.setdefault("S3_ADDRESSING_STYLE", "path")

os.environ.setdefault("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//")
os.environ.setdefault("CELERY_RESULT_BACKEND", "rpc://")

from app.models.base import Base
from app.core import config as config_module
from app.core.db import get_db


@pytest.fixture(scope="session")
def test_db_url(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture(scope="session")
def engine(test_db_url):
    return create_async_engine(test_db_url, future=True)


@pytest.fixture(scope="session")
def SessionLocal(engine):
    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="session", autouse=True)
def _patch_settings_db_url(test_db_url):
    os.environ["DB_URL"] = test_db_url
    try:
        config_module.get_settings.cache_clear()
    except Exception:
        pass
    yield


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _seed_active_image_model(_create_tables, SessionLocal):
    """
    Тесты /api/predictions ожидают, что в системе есть активная IMAGE_GENERATION модель.
    Мы отключаем lifespan, поэтому сидим это вручную.
    """
    from app.models.ml_model import MLModel, MLModelType

    async with SessionLocal() as session:
        q = select(MLModel).where(
            MLModel.model_type == MLModelType.IMAGE_GENERATION,
            MLModel.is_active.is_(True),
        )
        existing = (await session.execute(q)).scalars().first()
        if existing is None:
            session.add(
                MLModel(
                    name="test_image_model",
                    display_name="Test Image Model",
                    model_type=MLModelType.IMAGE_GENERATION,
                    engine="pytest",
                    version="1.0",
                    cost_credits=7,
                    is_active=True,
                )
            )
            await session.commit()


@pytest_asyncio.fixture()
async def db_session(SessionLocal):
    async with SessionLocal() as session:
        yield session


@pytest.fixture()
def app(SessionLocal):
    from app.run import create_app

    app = create_app()

    @asynccontextmanager
    async def _lifespan_override(_app):
        yield

    app.router.lifespan_context = _lifespan_override

    async def _override_get_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    return app


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def user_credentials():
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    password = "Password123!"
    return email, password


@pytest.fixture()
def register_user(client, user_credentials):
    def _register(email=None, password=None):
        if email is None or password is None:
            email, password = user_credentials
        return client.post("/api/auth/register", json={"email": email, "password": password})

    return _register


@pytest.fixture()
def login_user(client, register_user, user_credentials):
    def _login(email=None, password=None):
        if email is None or password is None:
            email, password = user_credentials

        register_user(email=email, password=password)

        return client.post(
            "/api/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    return _login


def _auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_headers(login_user):
    r = login_user()
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return _auth_headers(token)
