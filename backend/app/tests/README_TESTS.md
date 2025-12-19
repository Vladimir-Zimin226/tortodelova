# Tortodelova — тесты (pytest)

Этот документ описывает, как запускать тесты проекта и что именно они проверяют.

## Быстрый запуск

Из корня репозитория:

```bash
python -m pytest
```

Тихий режим:

```bash
python -m pytest -q
```

Запуск конкретного набора (пример):

```bash
python -m pytest -k "auth or predictions"
```

Остановиться на первой ошибке:

```bash
python -m pytest -x
```

## Красивый вывод

В проекте используется плагин **pytest-sugar**. Важно: у него **нет** опции `--sugar` — если плагин установлен, он подключается автоматически и вы увидите прогресс-бар/галочки как в логах.

Если хочется принудительно отключить sugar:

```bash
python -m pytest -p no:sugar
```

## Покрытие (coverage)

Покрытие по пакету `backend/app`:

```bash
python -m pytest --cov=backend/app --cov-report=term-missing
```

Убрать из отчёта полностью покрытые файлы:

```bash
python -m pytest --cov=backend/app --cov-report=term-missing:skip-covered
```

Сгенерировать HTML-отчёт:

```bash
python -m pytest --cov=backend/app --cov-report=html
```

После этого откройте `htmlcov/index.html`.

## Что покрывается тестами

Текущий набор тестов включает (по файлам в `backend/app/tests/`):

- **health**
  - `GET /health`

- **auth**
  - `POST /api/auth/register`
  - `POST /api/auth/login`
  - проверки валидации/ошибок (в т.ч. негативные сценарии)

- **user/me flow**
  - `GET /api/me/profile`
  - баланс: `GET /api/me/balance`, `POST /api/me/balance/deposit`
  - история транзакций: `GET /api/me/transactions`
  - базовый “пользовательский сценарий” (депозит → списание/предсказание → проверка истории)

- **predictions API**
  - `POST /api/predictions` — постановка в очередь, ошибки, проверка `model_id`
  - `GET /api/predictions` — список
  - `GET /api/predictions/{id}/image` — редирект на presigned URL
  - демо-режим:
    - `GET /api/predictions/demo/{task_id}` — preview демо-предсказания
    - `POST /api/predictions/demo/claim` — клонирование демо-предикта в историю текущего пользователя (через `PredictionService.clone_demo_prediction_for_user`)

- **Celery / очереди / задачи**
  - `prediction_queue_service.enqueue_image_generation` — проверка параметров `apply_async` (queue/routing_key/task_id/kwargs)
  - `ml_tasks.run_image_generation` — с моками `ml_service` и `storage_service`, плюс проверка, что ставится `db_tasks` с корректным payload
  - `db_tasks.save_prediction_result` — списание кредитов, создание `PredictionRequest`, идемпотентность по `task_id`

- **storage_service**
  - `StorageService.save_prediction_image` — формирование `s3_key`, вызовы `put_object_bytes` и `build_public_url`
  - `StorageService.clone_prediction_image` — вызов `copy_object`, формирование нового ключа и public_url

- **db seeding / инфраструктура**
  - проверки демо-сидинга/базовых данных (если тесты это ожидают)
  - базовые гарантии тестовой инфраструктуры (таблицы, зависимости)

## Как устроена тестовая среда (важно)

- Тесты используют **SQLite + aiosqlite** во временном файле (через `tmp_path_factory`).
  Почему файл, а не `:memory:`: приложение и тесты могут открывать разные соединения, и in-memory БД тогда “распадается”.

- В `conftest.py`:
  - подменяется `DB_URL` на тестовую БД;
  - очищается кеш `get_settings()` (через `lru_cache`) после подмены env;
  - создаются таблицы (`Base.metadata.create_all`);
  - **сидится активная IMAGE_GENERATION модель** (`MLModelType.IMAGE_GENERATION`, `is_active=True`), чтобы `POST /api/predictions` не падал с
    `No active image generation model configured`;
  - **lifespan отключается**, чтобы при создании `TestClient` не выполнялись “боевые” инициализации/сидинги.

- В тестах, где нужно, используются `monkeypatch`/моки:
  - чтобы не обращаться к реальному S3/MinIO;
  - чтобы не отправлять реальные задачи в RabbitMQ/Celery.

## Где смотреть/править

- Инфраструктура тестов: `backend/app/tests/conftest.py`
- Основные тесты API и сервисов: `backend/app/tests/test_*.py`