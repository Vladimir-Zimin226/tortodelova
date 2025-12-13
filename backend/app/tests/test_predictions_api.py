import os
import pytest
from sqlalchemy import select

from app.models.ml_model import MLModel, MLModelType
from app.models.prediction import PredictionRequest


def _create_success_prediction(
    *,
    user_id: int,
    prompt_ru: str,
    prompt_en: str,
    s3_key: str,
    public_url: str,
    credits_spent: int,
    task_id: str,
) -> PredictionRequest:
    """
    В проекте фабрика PredictionRequest.create_success() не принимает task_id/celery_task_id,
    но демо/preview эндпоинты и сервисы используют поле celery_task_id для поиска.

    Поэтому: создаём SUCCESS через фабрику и проставляем celery_task_id вручную.
    """
    pr = PredictionRequest.create_success(
        user_id=user_id,
        prompt_ru=prompt_ru,
        prompt_en=prompt_en,
        s3_key=s3_key,
        public_url=public_url,
        credits_spent=credits_spent,
    )
    pr.celery_task_id = task_id
    return pr


def test_create_prediction_enqueues_task(client, auth_headers, monkeypatch):
    dep = client.post(
        "/api/me/balance/deposit",
        headers=auth_headers,
        json={"amount": 50, "description": "Top up"},
    )
    assert dep.status_code == 200

    from app.api.routes import predictions as predictions_route

    fake_task_id = "11111111-2222-3333-4444-555555555555"
    monkeypatch.setattr(predictions_route, "enqueue_image_generation", lambda **kwargs: fake_task_id)

    r = client.post(
        "/api/predictions",
        headers=auth_headers,
        json={"prompt": "Нарисуй торт", "model_id": None},
    )
    assert r.status_code == 202, r.text
    j = r.json()
    assert j["queued"] is True
    assert j["task_id"] == fake_task_id
    assert j["cost_credits"] >= 0


def test_create_prediction_insufficient_balance(client, auth_headers):
    r = client.post("/api/predictions", headers=auth_headers, json={"prompt": "Торт"})
    assert r.status_code == 400
    assert "insufficient" in r.text.lower() or "credit" in r.text.lower()


def test_get_predictions_list_initially_empty(client, auth_headers):
    r = client.get("/api/predictions", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_predictions_model_id_not_found_returns_404(client, auth_headers):
    dep = client.post(
        "/api/me/balance/deposit",
        headers=auth_headers,
        json={"amount": 50, "description": "Top up"},
    )
    assert dep.status_code == 200, dep.text

    r = client.post("/api/predictions", headers=auth_headers, json={"prompt": "Test", "model_id": 999999})
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_predictions_model_id_wrong_type_returns_400(client, auth_headers, db_session):
    m = MLModel.create(
        name="test-translation",
        display_name="Test Translation",
        model_type=MLModelType.TRANSLATION,
        engine="pytest",
        version="1",
        cost_credits=1,
        is_active=True,
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)

    dep = client.post("/api/me/balance/deposit", headers=auth_headers, json={"amount": 50, "description": "Top up"})
    assert dep.status_code == 200, dep.text

    r = client.post("/api/predictions", headers=auth_headers, json={"prompt": "Test", "model_id": m.id})
    assert r.status_code == 400, r.text
    assert "image" in r.text.lower() or "generation" in r.text.lower()


@pytest.mark.asyncio
async def test_predictions_model_id_inactive_returns_400(client, auth_headers, db_session):
    m = MLModel.create(
        name="test-image-inactive",
        display_name="Test Image Inactive",
        model_type=MLModelType.IMAGE_GENERATION,
        engine="pytest",
        version="1",
        cost_credits=7,
        is_active=False,
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)

    dep = client.post("/api/me/balance/deposit", headers=auth_headers, json={"amount": 50, "description": "Top up"})
    assert dep.status_code == 200, dep.text

    r = client.post("/api/predictions", headers=auth_headers, json={"prompt": "Test", "model_id": m.id})
    assert r.status_code == 400, r.text
    assert "active" in r.text.lower()


@pytest.mark.asyncio
async def test_get_prediction_image_redirects_with_presigned_url(client, auth_headers, db_session, monkeypatch):
    prof = client.get("/api/me/profile", headers=auth_headers)
    assert prof.status_code == 200, prof.text
    user_id = prof.json()["id"]

    pr = _create_success_prediction(
        user_id=user_id,
        prompt_ru="Торт",
        prompt_en="Cake",
        s3_key="u/predictions/x.png",
        public_url="http://public/x.png",
        credits_spent=7,
        task_id="tid-img-1",
    )
    db_session.add(pr)
    await db_session.commit()
    await db_session.refresh(pr)

    from app.api.routes import predictions as predictions_route

    # routes/predictions.py ожидает dict с ключом "url":
    # presigned = presigned_get(...); url = presigned["url"]
    monkeypatch.setattr(
        predictions_route,
        "presigned_get",
        lambda key, expires=3600, **kwargs: {"url": f"http://presigned/{key}"},
    )

    r = client.get(
        f"/api/predictions/{pr.id}/image",
        headers=auth_headers,
        follow_redirects=False,
    )
    assert r.status_code in (302, 307), r.text
    assert r.headers.get("location") == f"http://presigned/{pr.s3_key}"


@pytest.mark.asyncio
async def test_demo_prediction_claim_clones_for_current_user(client, auth_headers, db_session, SessionLocal, monkeypatch):
    """
    В текущей реализации claim-эндпоинт может возвращать просто message (200 OK),
    а созданная запись может НЕ возвращаться в ответе.

    Поэтому:
    - проверяем preview (200),
    - делаем claim (200/201),
    - проверяем, что в БД появилась клонированная запись для текущего пользователя.

    ВАЖНО: claim выполняется в другом AsyncSession внутри приложения, поэтому
    проверку делаем через НОВУЮ сессию SessionLocal (иначе sqlite может показать "старый" снапшот).
    """
    from app.models.user import User, UserRole
    from app.api.routes import predictions as predictions_route
    from app.services.repositories import prediction_service as prediction_service_mod

    # На всякий случай: demo_email может читаться из env при инициализации settings
    os.environ["DEMO_EMAIL"] = "demo@example.com"

    monkeypatch.setattr(predictions_route.settings, "demo_email", "demo@example.com", raising=False)
    monkeypatch.setattr(prediction_service_mod.settings, "demo_email", "demo@example.com", raising=False)

    demo_user = User(email="demo@example.com", hashed_password="x", role=UserRole.USER, balance_credits=0)
    db_session.add(demo_user)
    await db_session.commit()
    await db_session.refresh(demo_user)

    demo_task_id = "demo-task-1"
    demo_pred = _create_success_prediction(
        user_id=demo_user.id,
        prompt_ru="Демо",
        prompt_en="Demo",
        s3_key="demo/predictions/demo.png",
        public_url="http://public/demo.png",
        credits_spent=0,
        task_id=demo_task_id,
    )
    db_session.add(demo_pred)
    await db_session.commit()
    await db_session.refresh(demo_pred)

    async def _fake_clone_prediction_image(*, source_s3_key: str, target_user_id: int):
        return (
            f"user-{target_user_id}/predictions/cloned.png",
            f"http://public/user-{target_user_id}/predictions/cloned.png",
        )

    monkeypatch.setattr(
        prediction_service_mod.storage_service,
        "clone_prediction_image",
        _fake_clone_prediction_image,
    )

    preview = client.get(f"/api/predictions/demo/{demo_task_id}", headers=auth_headers)
    assert preview.status_code == 200, preview.text

    claim = client.post(
        "/api/predictions/demo/claim",
        headers=auth_headers,
        json={"task_id": demo_task_id},
    )
    assert claim.status_code in (200, 201), claim.text

    current_user_id = client.get("/api/me/profile", headers=auth_headers).json()["id"]

    async with SessionLocal() as verify_session:
        res = await verify_session.execute(
            select(PredictionRequest).where(PredictionRequest.user_id == current_user_id)
        )
        preds = res.scalars().all()

    assert any(
        "cloned.png" in (p.public_url or "") or "cloned.png" in (p.s3_key or "")
        for p in preds
    ), f"Expected cloned prediction for user_id={current_user_id}, got: {[p.public_url for p in preds]}"

    cloned = next(p for p in preds if "cloned.png" in (p.public_url or "") or "cloned.png" in (p.s3_key or ""))
    assert getattr(cloned, "credits_spent", 0) == 0
