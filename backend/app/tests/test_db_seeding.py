import pytest
from sqlalchemy import delete, select

from app.models.user import User, UserRole
from app.models.ml_model import MLModel, MLModelType


@pytest.mark.asyncio
async def test_seed_initial_users_creates_admin_and_user(engine, SessionLocal, monkeypatch):
    import app.core.db as db_mod

    # Point db_mod to the test engine/sessionmaker used by pytest
    monkeypatch.setattr(db_mod, "engine", engine, raising=False)
    monkeypatch.setattr(db_mod, "AsyncSessionLocal", SessionLocal, raising=False)

    async with SessionLocal() as session:
        await session.execute(delete(User))
        await session.commit()

    await db_mod.seed_initial_users()

    async with SessionLocal() as session:
        res = await session.execute(select(User))
        users = res.scalars().all()
        assert len(users) >= 2
        roles = {u.role for u in users}
        assert UserRole.ADMIN in roles
        assert UserRole.USER in roles


@pytest.mark.asyncio
async def test_seed_initial_ml_models_creates_defaults(engine, SessionLocal, monkeypatch):
    import app.core.db as db_mod

    monkeypatch.setattr(db_mod, "engine", engine, raising=False)
    monkeypatch.setattr(db_mod, "AsyncSessionLocal", SessionLocal, raising=False)

    async with SessionLocal() as session:
        await session.execute(delete(MLModel))
        await session.commit()

    await db_mod.seed_initial_ml_models()

    async with SessionLocal() as session:
        res = await session.execute(select(MLModel))
        models = res.scalars().all()
        assert len(models) >= 1
        assert any(m.model_type == MLModelType.IMAGE_GENERATION for m in models)
