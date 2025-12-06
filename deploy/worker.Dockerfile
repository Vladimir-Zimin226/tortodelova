FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY deploy/requirements.worker.txt /app/requirements.worker.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.worker.txt

COPY backend/app /app/app

CMD ["celery", "-A", "app.celery_app:celery_app", "worker", "--loglevel=INFO"]
