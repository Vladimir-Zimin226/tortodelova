from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.user import UserRole
from app.models.transaction import TransactionType
from app.models.prediction import PredictionStatus
from app.models.ml_model import MLModelType
from app.services.repositories.user_service import user_service
from app.services.repositories.transaction_service import transaction_service
from app.services.repositories.prediction_service import prediction_service
from app.services.repositories.ml_model_service import ml_model_service

logger = logging.getLogger("demo-crud-scenario")
logging.basicConfig(level=logging.INFO)


ADMIN_EMAIL = "admin@user.ru"   # как в seed_initial_users
TEST_EMAIL = "test@user.ru"     # как в seed_initial_users


async def ensure_seed_users(session: AsyncSession) -> None:
    """
    Убеждаемся, что базовые пользователи существуют.
    Если по какой-то причине их нет — создаём.
    """
    admin = await user_service.get_by_email(session, ADMIN_EMAIL)
    if not admin:
        admin = await user_service.create(
            session,
            email=ADMIN_EMAIL,
            hashed_password="seeded-admin-password",  # тут неважно, для логина есть отдельный поток
            role=UserRole.ADMIN,
            balance_credits=0,
        )
        logger.info("Seed admin user created: id=%s email=%s", admin.id, admin.email)
    else:
        logger.info("Seed admin user already exists: id=%s email=%s", admin.id, admin.email)

    test_user = await user_service.get_by_email(session, TEST_EMAIL)
    if not test_user:
        test_user = await user_service.create(
            session,
            email=TEST_EMAIL,
            hashed_password="seeded-test-password",
            role=UserRole.USER,
            balance_credits=0,
        )
        logger.info("Seed test user created: id=%s email=%s", test_user.id, test_user.email)
    else:
        logger.info("Seed test user already exists: id=%s email=%s", test_user.id, test_user.email)


async def run_user_crud_scenario(session: AsyncSession) -> None:
    """
    Полный CRUD-цикл для временного пользователя:
    create -> read -> update -> list -> delete.
    """
    logger.info("=== USER CRUD SCENARIO: START ===")

    unique_suffix = uuid.uuid4().hex[:8]
    email = f"crud-user-{unique_suffix}@example.com"

    # CREATE
    user = await user_service.create(
        session,
        email=email,
        hashed_password="demo-hash",
        role=UserRole.USER,
        balance_credits=10,
    )

    # READ (get by id)
    _ = await user_service.get(session, user.id)

    # UPDATE (role + баланс)
    user = await user_service.update(
        session,
        user.id,
        role=UserRole.ADMIN,
        balance_credits=20,
    )

    # LIST
    users = await user_service.list(session, limit=5)
    logger.info(
        "User CRUD: sample list (first 5 users): %s",
        [u.email for u in users],
    )

    # DELETE
    deleted = await user_service.delete(session, user.id)
    logger.info(
        "User CRUD: deleted temp user id=%s email=%s success=%s",
        user.id,
        email,
        deleted,
    )

    logger.info("=== USER CRUD SCENARIO: END ===")


async def run_ml_model_crud_scenario(session: AsyncSession) -> int:
    """
    CRUD-сценарий для MLModel:
    create (2 шт) -> get -> update -> list -> delete (одной из моделей).

    Возвращает стоимость (cost_credits) для модели генерации изображений,
    чтобы далее использовать её для списания кредитов в баланс-сценарии.
    """
    logger.info("=== ML MODEL CRUD SCENARIO: START ===")

    suffix = uuid.uuid4().hex[:6]

    # CREATE: модель перевода
    translation_model = await ml_model_service.create(
        session,
        name=f"demo-translation-{suffix}",
        display_name="Demo Translation RU→EN",
        model_type=MLModelType.TRANSLATION,
        engine="huggingface",
        version="ru-en-demo",
        cost_credits=0,
        is_active=True,
    )

    # CREATE: модель генерации изображений
    image_model = await ml_model_service.create(
        session,
        name=f"demo-image-{suffix}",
        display_name="Demo Image Generator",
        model_type=MLModelType.IMAGE_GENERATION,
        engine="diffusers",
        version="v-demo",
        cost_credits=25,
        is_active=True,
    )

    # GET
    _ = await ml_model_service.get(session, image_model.id)

    # UPDATE (например, увеличить стоимость генерации)
    image_model = await ml_model_service.update(
        session,
        image_model.id,
        cost_credits=image_model.cost_credits + 5,
    )

    # LIST
    models = await ml_model_service.list(session)
    logger.info(
        "MLModel CRUD: total models=%s names=%s",
        len(models),
        [m.name for m in models],
    )

    # DELETE одну из моделей (перевода) для демонстрации полного CRUD
    deleted = await ml_model_service.delete(session, translation_model.id)
    logger.info(
        "MLModel CRUD: deleted translation_model id=%s success=%s",
        translation_model.id,
        deleted,
    )

    logger.info(
        "=== ML MODEL CRUD SCENARIO: END (image_model_cost=%s) ===",
        image_model.cost_credits,
    )

    # Стоимость генерации будем использовать как сумму списания
    return image_model.cost_credits


async def run_balance_and_transactions_scenario(
    session: AsyncSession,
    *,
    image_generation_cost: int,
) -> None:
    """
    Сценарий:
    - берём тестового пользователя;
    - пополняем баланс;
    - списываем кредиты за генерацию изображения (по стоимости ML-модели);
    - получаем историю транзакций.
    """
    logger.info("=== BALANCE & TRANSACTIONS SCENARIO: START ===")

    user = await user_service.get_by_email(session, TEST_EMAIL)
    if not user:
        raise RuntimeError(f"Test user {TEST_EMAIL!r} not found. Run ensure_seed_users first.")

    logger.info(
        "Using test user for balance scenario: id=%s email=%s balance=%s",
        user.id,
        user.email,
        user.balance_credits,
    )

    # CREDIT — пополняем баланс с запасом
    top_up_amount = max(image_generation_cost * 2, 50)
    user, tx_credit = await user_service.change_balance_with_transaction(
        session,
        user_id=user.id,
        amount=top_up_amount,
        tx_type=TransactionType.CREDIT,
        description="Demo top-up via scenario",
    )

    logger.info(
        "Balance scenario: credited %s credits (tx_id=%s), new_balance=%s",
        tx_credit.amount,
        tx_credit.id,
        user.balance_credits,
    )

    # DEBIT — списываем стоимость одной генерации изображения
    user, tx_debit = await user_service.change_balance_with_transaction(
        session,
        user_id=user.id,
        amount=image_generation_cost,
        tx_type=TransactionType.DEBIT,
        description="Demo image generation charge (by MLModel cost)",
    )

    logger.info(
        "Balance scenario: debited %s credits (tx_id=%s), new_balance=%s",
        tx_debit.amount,
        tx_debit.id,
        user.balance_credits,
    )

    # LIST TRANSACTIONS
    txs = await transaction_service.list_by_user(session, user_id=user.id)
    logger.info(
        "Transactions for user id=%s email=%s: count=%s ids=%s",
        user.id,
        user.email,
        len(txs),
        [t.id for t in txs],
    )

    logger.info(
        "Final balance for user id=%s email=%s: %s",
        user.id,
        user.email,
        user.balance_credits,
    )

    logger.info("=== BALANCE & TRANSACTIONS SCENARIO: END ===")


async def run_prediction_crud_scenario(session: AsyncSession) -> None:
    """
    CRUD-сценарий для PredictionRequest:
    create -> read -> update -> list_by_user -> delete.
    """
    logger.info("=== PREDICTION CRUD SCENARIO: START ===")

    user = await user_service.get_by_email(session, TEST_EMAIL)
    if not user:
        raise RuntimeError(f"Test user {TEST_EMAIL!r} not found")

    # CREATE
    prediction = await prediction_service.create(
        session=session,
        user_id=user.id,
        prompt_ru="кот на велосипеде",
        prompt_en="a cat riding a bike, illustration, 4k",
        s3_key="demo/crud_scenario/cat_bike.png",
        public_url="https://example.com/demo/cat_bike.png",
        credits_spent=25,
        status=PredictionStatus.PENDING,
    )

    # READ
    _ = await prediction_service.get(session, prediction.id)

    # UPDATE (например, статус)
    prediction = await prediction_service.update(
        session,
        prediction.id,
        status=PredictionStatus.SUCCESS,  # должно совпадать с одним из значений Enum в модели
    )

    # LIST BY USER
    predictions = await prediction_service.list_by_user(session, user_id=user.id)
    logger.info(
        "Predictions for user id=%s email=%s: count=%s ids=%s",
        user.id,
        user.email,
        len(predictions),
        [p.id for p in predictions],
    )

    # DELETE (чтобы показать полный CRUD)
    deleted = await prediction_service.delete(session, prediction.id)
    logger.info(
        "Prediction CRUD: deleted prediction id=%s success=%s",
        prediction.id,
        deleted,
    )

    logger.info("=== PREDICTION CRUD SCENARIO: END ===")


async def main() -> None:
    """
    Главная точка входа сценария.
    Запускать при запущенном docker-compose backend.

    Команда запуска:
    docker-compose exec app python -m app.scripts.demo_crud_scenario
    """
    logger.info("=== DEMO CRUD SCENARIO: START ===")
    async with AsyncSessionLocal() as session:
        # один общий транзакционный блок на весь сценарий
        async with session.begin():
            await ensure_seed_users(session)
            await run_user_crud_scenario(session)
            image_model_cost = await run_ml_model_crud_scenario(session)
            await run_balance_and_transactions_scenario(
                session,
                image_generation_cost=image_model_cost,
            )
            await run_prediction_crud_scenario(session)

    logger.info("=== DEMO CRUD SCENARIO: DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
