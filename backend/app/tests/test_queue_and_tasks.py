import types
import pytest

def test_enqueue_image_generation_calls_apply_async(monkeypatch):
    from app.services import prediction_queue_service as q

    called = {}

    class DummyAsync:
        def apply_async(self, *, kwargs, queue, routing_key, task_id):
            called["kwargs"] = kwargs
            called["queue"] = queue
            called["routing_key"] = routing_key
            called["task_id"] = task_id

    # patch uuid and task object
    monkeypatch.setattr(q.uuid, "uuid4", lambda: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    monkeypatch.setattr(q, "run_image_generation", DummyAsync())

    tid = q.enqueue_image_generation(user_id=1, prompt_ru="привет", credits_spent=7)

    assert tid == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert called["queue"] == "ml_tasks"
    assert called["routing_key"] == "ml.generate"
    assert called["task_id"] == tid
    assert called["kwargs"]["payload"]["user_id"] == 1
    assert called["kwargs"]["payload"]["prompt_ru"] == "привет"
    assert called["kwargs"]["payload"]["credits_spent"] == 7
    assert called["kwargs"]["payload"]["task_id"] == tid

def test_ml_task_builds_result_and_enqueues_db_task(monkeypatch):
    from app.tasks import ml_tasks

    async def fake_translate(prompt_ru: str) -> str:
        return "hello cake"

    async def fake_generate(prompt_en: str) -> bytes:
        return b"PNGDATA"

    async def fake_save(*, image_bytes: bytes, user_id: int):
        assert image_bytes == b"PNGDATA"
        assert user_id == 123
        return ("user-123/predictions/x.png", "http://localhost:9000/bucket/x.png")

    monkeypatch.setattr(ml_tasks.ml_service, "translate_ru_to_en", fake_translate)
    monkeypatch.setattr(ml_tasks.ml_service, "generate_image", fake_generate)
    monkeypatch.setattr(ml_tasks.storage_service, "save_prediction_image", fake_save)

    called = {}
    class DummyDbTask:
        def apply_async(self, *, kwargs, queue, routing_key):
            called["kwargs"] = kwargs
            called["queue"] = queue
            called["routing_key"] = routing_key

    import app.tasks.db_tasks as db_tasks_mod
    monkeypatch.setattr(db_tasks_mod, "save_prediction_result", DummyDbTask())

    payload = {"user_id": 123, "prompt_ru": "нарисуй торт", "credits_spent": 5, "task_id": "tid-1"}
    result = ml_tasks.run_image_generation(payload)

    assert result["user_id"] == 123
    assert result["prompt_ru"] == "нарисуй торт"
    assert result["prompt_en"] == "hello cake"
    assert result["credits_spent"] == 5
    assert result["task_id"] == "tid-1"
    assert "s3_key" in result and "public_url" in result

    assert called["queue"] == "db_tasks"
    assert called["routing_key"] == "db.save"
    assert called["kwargs"]["payload"]["prompt_en"] == "hello cake"

def test_db_task_is_idempotent_and_debits_once(engine, monkeypatch, test_db_url):
    import asyncio
    from sqlalchemy import select
    from app.models.user import User, UserRole
    from app.models.transaction import Transaction
    from app.models.prediction import PredictionRequest
    import app.tasks.db_tasks as db_tasks
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    monkeypatch.setattr(db_tasks.settings, "db_url", test_db_url)

    async def _prepare_and_assert():
        SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        async with SessionLocal() as session:
            u = User(email="idempo@example.com", hashed_password="x", role=UserRole.USER, balance_credits=20)
            session.add(u)
            await session.commit()
            await session.refresh(u)
            return u.id

    user_id = asyncio.run(_prepare_and_assert())

    payload = {
        "user_id": user_id,
        "prompt_ru": "торт",
        "prompt_en": "cake",
        "s3_key": "k1",
        "public_url": "http://x/k1",
        "credits_spent": 7,
        "task_id": "task-xyz",
    }

    r1 = db_tasks.save_prediction_result(payload)
    r2 = db_tasks.save_prediction_result(payload)

    assert r1["status"] == "success"
    assert r2.get("already_exists") is True

    import asyncio as _aio
    async def _check():
        SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        async with SessionLocal() as session:
            u = await session.get(User, user_id)
            assert u.balance_credits == 13

            txs = (await session.execute(select(Transaction).where(Transaction.user_id == user_id))).scalars().all()
            assert len(txs) == 1

            preds = (await session.execute(select(PredictionRequest).where(PredictionRequest.user_id == user_id))).scalars().all()
            assert len(preds) == 1

    _aio.run(_check())

