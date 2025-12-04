from __future__ import annotations

import logging
from typing import Final

logger = logging.getLogger(__name__)


class MLService:
    """
    Сервис-обёртка над ML-моделями.

    Сейчас реализован в минимальном виде:
    - translate_ru_to_en: "псевдо-перевод" (для отладки очередей);
    - generate_image: возвращает байты, основанные на prompt_en.

    В будущем сюда интегрируем:
    - Helsinki-NLP/opus-mt-ru-en для перевода;
    - DreamShaper / любую SD 1.5 модель для генерации.
    """

    _dummy_header: Final[bytes] = b"FAKE_IMAGE_HEADER"

    async def translate_ru_to_en(self, prompt_ru: str) -> str:
        """
        Перевод RU -> EN.

        Пока: возвращаем тот же промпт, можно добавить простую пометку.
        """
        prompt_ru = prompt_ru.strip()
        if not prompt_ru:
            raise ValueError("Промпт не может быть пустым.")

        # Здесь в будущем будет реальный вызов переводчика.
        prompt_en = prompt_ru  # "псевдоперевод"
        logger.info("MLService.translate_ru_to_en: %r -> %r", prompt_ru, prompt_en)
        return prompt_en

    async def generate_image(self, prompt_en: str) -> bytes:
        """
        Генерация изображения по англоязычному промпту.

        Пока: возвращаем "фейковое" содержимое (заголовок + текст промпта).
        Этого достаточно, чтобы протестировать:
        - работу Celery;
        - запись в хранилище;
        - запись в БД.
        """
        prompt_en = prompt_en.strip()
        if not prompt_en:
            raise ValueError("Англоязычный промпт не может быть пустым.")

        logger.info("MLService.generate_image: prompt_en=%r", prompt_en)

        # В реальности: вызов диффузионной модели и JPEG/PNG байты.
        image_bytes = self._dummy_header + prompt_en.encode("utf-8")
        return image_bytes


ml_service = MLService()
