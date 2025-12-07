from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Final

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MLService:
    """
    Сервис-обёртка над ML-моделями.

    Используются:
    - Helsinki-NLP/opus-mt-ru-en для перевода RU -> EN;
    - DreamShaper v8 (SD 1.5, diffusers) для генерации.

    Модели загружаются при первом вызове (lazy).
    """

    def __init__(self) -> None:
        self._device_str: Final[str] = getattr(settings, "torch_device", "cpu")

        # Переводчик
        self._translator_tokenizer = None  # type: ignore[assignment]
        self._translator_model = None      # type: ignore[assignment]

        # Диффузионная модель
        self._sd_pipeline = None           # type: ignore[assignment]

    # ---------- ВСПОМОГАТЕЛЬНОЕ ----------

    def _get_device(self):
        """
        Cоздаём torch.device, импортируя torch только внутри воркера (lazy).
        """
        import torch

        return torch.device(self._device_str)

    # ---------- ПЕРЕВОД RU -> EN ----------

    def _ensure_translator_loaded(self) -> None:
        """
        Загружаем Helsinki-NLP/opus-mt-ru-en (lazy).
        """
        if self._translator_model is not None:
            return

        from transformers import MarianMTModel, MarianTokenizer  # локальный импорт
        import torch

        model_dir = Path(settings.translator_model_dir)
        logger.info("MLService: loading translator from %s", model_dir)

        tokenizer = MarianTokenizer.from_pretrained(model_dir)
        model = MarianMTModel.from_pretrained(model_dir)

        model.to("cpu")  # переводчик работает на CPU
        model.eval()

        # сохраняем
        self._translator_tokenizer = tokenizer
        self._translator_model = model

        logger.info("MLService: translator loaded successfully")

    async def translate_ru_to_en(self, prompt_ru: str) -> str:
        """
        Перевод RU -> EN через Helsinki-NLP/opus-mt-ru-en.
        """
        import torch

        prompt_ru = (prompt_ru or "").strip()
        if not prompt_ru:
            raise ValueError("Промпт не может быть пустым.")

        self._ensure_translator_loaded()
        assert self._translator_tokenizer is not None
        assert self._translator_model is not None

        tokenizer = self._translator_tokenizer
        model = self._translator_model

        batch = tokenizer(
            prompt_ru,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )

        with torch.no_grad():
            generated = model.generate(
                **batch,
                max_new_tokens=256,
                num_beams=4,
                no_repeat_ngram_size=3,
            )

        prompt_en = tokenizer.decode(
            generated[0],
            skip_special_tokens=True,
        ).strip()

        if not prompt_en:
            prompt_en = prompt_ru

        logger.info(
            "MLService.translate_ru_to_en: %r -> %r",
            prompt_ru,
            prompt_en,
        )
        return prompt_en

    # ---------- DREAMSHAPER (SD 1.5) ----------

    def _ensure_sd_pipeline_loaded(self) -> None:
        """
        Загрузка DreamShaper v8 (Stable Diffusion 1.5, diffusers) (lazy).
        """
        if self._sd_pipeline is not None:
            return

        import torch
        from diffusers import StableDiffusionPipeline  # локальный импорт

        model_dir = Path(settings.dreamshaper_model_dir)
        device = self._get_device()
        logger.info(
            "MLService: loading DreamShaper pipeline from %s on device %s",
            model_dir,
            device,
        )

        dtype = torch.float16 if device.type == "cuda" else torch.float32

        pipe = StableDiffusionPipeline.from_pretrained(
            model_dir,
            torch_dtype=dtype,
            safety_checker=None,  # можно включить при необходимости
        )
        pipe.to(device)

        try:
            pipe.enable_attention_slicing("max")
        except Exception:  # noqa: BLE001
            logger.warning("MLService: enable_attention_slicing failed", exc_info=True)

        self._sd_pipeline = pipe

        logger.info("MLService: DreamShaper pipeline loaded successfully")

    async def generate_image(
        self,
        prompt_en: str,
        width: int = 384,
        height: int = 384,
        num_inference_steps: int = 20,
        guidance_scale: float = 7.5,
    ) -> bytes:
        """
        Генерация PNG-байт по англоязычному промпту.
        """
        import torch  # локальный импорт

        prompt_en = (prompt_en or "").strip()
        if not prompt_en:
            raise ValueError("Англоязычный промпт не может быть пустым.")

        # SD 1.5 ожидает размеры кратные 8
        if width % 8 != 0 or height % 8 != 0:
            raise ValueError("width/height должны быть кратны 8 (сейчас %s×%s)." % (width, height))

        self._ensure_sd_pipeline_loaded()
        assert self._sd_pipeline is not None

        device = self._get_device()
        pipe = self._sd_pipeline

        logger.info(
            "MLService.generate_image: prompt_en=%r size=%sx%s steps=%s cfg=%s",
            prompt_en,
            width,
            height,
            num_inference_steps,
            guidance_scale,
        )

        # фиксированный сид для воспроизводимости (по желанию можно параметризовать)
        generator = torch.Generator(device=device).manual_seed(42)

        with torch.no_grad():
            result = pipe(
                prompt_en,
                width=width,
                height=height,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                generator=generator,
            )

        image = result.images[0]  # PIL.Image.Image

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        data = buf.getvalue()

        logger.info(
            "MLService.generate_image: generated %s bytes for prompt %r",
            len(data),
            prompt_en,
        )
        return data


ml_service = MLService()
