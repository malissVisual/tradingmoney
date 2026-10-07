FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/bot.db
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY texts ./texts

VOLUME /data
CMD ["python", "-m", "bot"]
