FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin bot

COPY bots/buyer_bot/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --requirement /tmp/requirements.txt

COPY --chown=bot:bot bots/b2b_common/ /app/b2b_common/
COPY --chown=bot:bot bots/buyer_bot/ /app/bot/

USER bot
WORKDIR /app/bot
CMD ["python", "main.py"]

