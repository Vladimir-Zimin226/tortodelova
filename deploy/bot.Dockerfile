FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY deploy/requirements.bot.txt /app/requirements.bot.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.bot.txt

COPY backend/app /app/app

CMD ["python", "-m", "app.telegram.bot"]