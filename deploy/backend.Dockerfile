FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    rustc \
    cargo \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/requirements.backend.txt /app/requirements.backend.txt
RUN pip install --no-cache-dir -r /app/requirements.backend.txt

COPY backend/app /app/app

CMD ["uvicorn", "app.run:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
