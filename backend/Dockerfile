FROM python:3.12-slim

# Рабочая директория внутри контейнера
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Системные зависимости (если понадобятся для asyncpg и т.п.)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости backend
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Копируем приложение (для прода; в dev переопределим volume'ом)
COPY backend/app /app/app

# Команда по умолчанию:
# Внутри контейнера пакет называется "app", а main — /app/app/main.py
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
