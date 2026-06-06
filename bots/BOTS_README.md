# KULCHA Bots (`bots`)

В проекте используются Telegram-боты на `aiogram 3.x`:

- `user_bot` — клиентский бот (регистрация, переход в Mini App, статус заказа);
- `admin_bot` — бот персонала ресторана;
- `superadmin_bot` — бот платформы и служебных команд;
- `support_bot` — бот поддержки с интеграцией в Telegram-группу.
- `channel_subscriptions_bot` — автономный бот для уведомлений о подписках и отписках в канале.

## Общие требования

- Python 3.10+
- Запущенный backend (`http://localhost:8000/api/v1` локально)
- Настроенные `.env` файлы в директориях ботов

## Быстрый запуск любого бота

```bash
cd bots/<bot_name>
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

`<bot_name>`: `user_bot`, `admin_bot`, `superadmin_bot`, `support_bot`, `channel_subscriptions_bot`.

## Переменные окружения

### `user_bot`

- `KULCHA_USER_BOT_TOKEN`
- `KULCHA_API_BASE` (обычно `http://localhost:8000/api/v1`)
- `KULCHA_USER_MINI_APP_URL`
- `KULCHA_USER_MINI_APP_VERSION` (опционально)
- `KULCHA_SUPPORT_LINK`
- `KULCHA_BOT_API_SECRET` (если backend это требует)

### `admin_bot`

- `KULCHA_ADMIN_BOT_TOKEN`
- `KULCHA_API_BASE`
- `KULCHA_ADMIN_MINI_APP_URL`
- `KULCHA_SUPPORT_LINK`
- `KULCHA_INTERNAL_API_SECRET` (должен совпадать с backend)

### `superadmin_bot`

- `KULCHA_SUPERADMIN_BOT_TOKEN`
- `KULCHA_API_BASE`
- `KULCHA_SUPERADMIN_ALLOWED_IDS` (опционально)
- `KULCHA_SUPERADMIN_MINI_APP_URL`
- `KULCHA_SUPPORT_LINK`

### `support_bot`

- `KULCHA_SUPPORT_BOT_TOKEN`
- `KULCHA_API_BASE`
- `KULCHA_INTERNAL_API_SECRET` (должен совпадать с backend)
- `KULCHA_SUPPORT_GROUP_ID` (ID супергруппы для тикетов)

### `channel_subscriptions_bot`

- `KULCHA_CHANNEL_SUBSCRIPTIONS_BOT_TOKEN` (по умолчанию задан в `config.py`)
- `KULCHA_CHANNEL_SUBSCRIPTIONS_ADMIN_ID` (по умолчанию `1038155901`)
- `KULCHA_CHANNEL_SUBSCRIPTIONS_DB` (опционально)
- `KULCHA_CHANNEL_SUBSCRIPTIONS_TZ` (опционально, по умолчанию `Europe/Moscow`)

## Что делает каждый бот

- `user_bot`: онбординг клиента, запрос контакта, открытие клиентского Mini App, запрос статуса заказа.
- `admin_bot`: быстрый вход в admin Mini App, сервисные действия по заказам.
- `superadmin_bot`: команды мониторинга (`/health`, `/stats`) и выборка сущностей (`/order`, `/restaurant`, `/user`).
- `support_bot`: создание/сопровождение тикетов и пересылка в группу поддержки.
- `channel_subscriptions_bot`: запоминает владельца через `/start`, привязывается к каналу после добавления администратором и отправляет владельцу события подписки/отписки.

## Проверка работоспособности

1. Запустить backend (`backend/BACKEND_README.md`).
2. Запустить нужного бота.
3. Отправить `/start` соответствующему боту в Telegram.
4. Проверить логи бота и ответы API.
