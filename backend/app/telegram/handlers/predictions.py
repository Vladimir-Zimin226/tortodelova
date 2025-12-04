from __future__ import annotations

from typing import List

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.core.db import AsyncSessionLocal
from app.models.ml_model import MLModelType
from app.services.prediction_queue_service import enqueue_image_generation
from app.services.repositories.user_service import user_service
from app.services.repositories.prediction_service import prediction_service
from app.services.repositories.ml_model_service import ml_model_service
from app.telegram.handlers.auth import get_backend_user_id

router = Router(name="tg_predictions")


@router.message(Command("predict"))
async def cmd_predict(message: Message) -> None:
    """
    Создать новый запрос на генерацию.

    Теперь:
    - проверяем, что пользователь залогинен;
    - проверяем, что есть активная image-модель;
    - проверяем, что на балансе достаточно кредитов;
    - ставим задачу в Celery (ml_tasks -> db_tasks);
    - результат можно посмотреть через /predictions и /prediction.
    """
    backend_user_id = get_backend_user_id(message.from_user.id)
    if backend_user_id is None:
        await message.answer("Сначала выполните /register или /login.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: <code>/predict ваш промпт</code>")
        return

    prompt = parts[1].strip()
    if not prompt:
        await message.answer("Промпт не должен быть пустым.")
        return

    # Проверяем пользователя, активную модель и баланс
    async with AsyncSessionLocal() as session:
        user = await user_service.get(session, backend_user_id)
        if not user:
            await message.answer(
                "Пользователь не найден. Попробуйте снова выполнить /login."
            )
            return

        # Берём первую активную модель для генерации изображений
        image_model = await ml_model_service.get_first_active_by_type(
            session,
            MLModelType.IMAGE_GENERATION,
        )
        if not image_model:
            await message.answer(
                "Нет активной модели генерации изображений. "
                "Обратитесь к администратору."
            )
            return

        cost = image_model.cost_credits or 0

        if user.balance_credits < cost:
            await message.answer(
                "Недостаточно кредитов для генерации.\n"
                f"Нужно: <b>{cost}</b>, у вас: <b>{user.balance_credits}</b>.\n"
                "Пополните баланс через /deposit."
            )
            return

    # Ставим задачу в Celery (синхронная функция, Celery сам async-часть сделает)
    task_id = enqueue_image_generation(
        user_id=backend_user_id,
        prompt_ru=prompt,
        credits_spent=cost,
    )

    await message.answer(
        "Запрос на генерацию поставлен в очередь ✅\n\n"
        f"Промпт: <code>{prompt}</code>\n"
        f"Стоимость: <b>{cost}</b> кредитов (будут списаны после успешной генерации).\n"
        f"ID задачи: <code>{task_id}</code>\n\n"
        "Статус и результат можно посмотреть:\n"
        "• /predictions — последние запросы\n"
        "• /prediction &lt;id&gt; — детали конкретного запроса"
    )


@router.message(Command("predictions"))
async def cmd_list_predictions(message: Message) -> None:
    """
    Показать последние запросы на предсказания.
    """
    backend_user_id = get_backend_user_id(message.from_user.id)
    if backend_user_id is None:
        await message.answer("Сначала выполните /register или /login.")
        return

    async with AsyncSessionLocal() as session:
        preds = await prediction_service.list_by_user(
            session,
            user_id=backend_user_id,
            limit=5,
            offset=0,
        )

    if not preds:
        await message.answer("У вас пока нет запросов на предсказания.")
        return

    lines: List[str] = ["Последние запросы на генерацию:"]
    for p in preds:
        lines.append(
            f"ID {p.id}: {p.status} — {p.credits_spent} кредит(ов), "
            f"prompt: {p.prompt_ru[:50]}..."
        )

    await message.answer("\n".join(lines))


@router.message(Command("prediction"))
async def cmd_prediction_details(message: Message) -> None:
    """
    Показать детали конкретного запроса по ID.
    """
    backend_user_id = get_backend_user_id(message.from_user.id)
    if backend_user_id is None:
        await message.answer("Сначала выполните /register или /login.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: <code>/prediction 123</code>")
        return

    try:
        prediction_id = int(parts[1].strip())
    except ValueError:
        await message.answer("ID должен быть целым числом.")
        return

    async with AsyncSessionLocal() as session:
        prediction = await prediction_service.get(session, prediction_id)

    if not prediction or prediction.user_id != backend_user_id:
        await message.answer("Запрос с таким ID не найден.")
        return

    await message.answer(
        f"ID: <code>{prediction.id}</code>\n"
        f"Статус: <b>{prediction.status}</b>\n"
        f"Промпт (RU): <code>{prediction.prompt_ru}</code>\n"
        f"Промпт (EN): <code>{prediction.prompt_en}</code>\n"
        f"URL: {prediction.public_url}\n"
        f"Списано кредитов: <b>{prediction.credits_spent}</b>.\n"
    )
