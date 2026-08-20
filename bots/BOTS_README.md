# Kulcha Market Bots (`bots`)

В проекте используются Telegram-боты на `aiogram 3.x`:

- `user_bot` — клиентский бот (регистрация, переход в Mini App, статус заказа);
- `admin_bot` — бот персонала ресторана;
- `superadmin_bot` — бот платформы и служебных команд;

Отдельный KULCHA B2B contour использует:

- `buyer_bot` — invite-only регистрация покупателя, каталог, заказы и подписка;
- `seller_bot` — регистрация поставщика, предложения и подготовка заказов;
- `b2b_admin_bot` — оперативные уведомления и подтверждаемые quick actions;
- `b2b_common` — общий config/internal API/link слой без bot tokens в коде.

B2B-боты запускаются через Compose profile `b2b`: local default — long polling,
production — HTTPS webhook (`*_BOT_MODE=webhook`) с отдельным secret. Admin bot
не стартует при пустом `ADMIN_TELEGRAM_IDS`; buyer/seller принимают только контакт,
у которого `contact.user_id` совпадает с отправителем. Все webhook adapters требуют
Redis для дедупликации update; buyer дополнительно хранит там FSM. См.
`../B2B_README.md`.

Поддержка в маркетовых ботах открывается ссылкой `MARKET_SUPPORT_LINK` на общий support bot Kulcha.

## Общие требования

- Python 3.10+ для legacy bots; Python 3.12 для B2B bots
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

`<bot_name>`: `user_bot`, `admin_bot`, `superadmin_bot`.

## Переменные окружения

### `user_bot`

- `MARKET_USER_BOT_TOKEN`
- `MARKET_API_BASE` (обычно `http://localhost:8000/api/v1`)
- `MARKET_USER_MINI_APP_URL`
- `MARKET_USER_MINI_APP_VERSION` (опционально)
- `MARKET_SUPPORT_LINK`
- `MARKET_BOT_API_SECRET` (если backend это требует)

### `admin_bot`

- `MARKET_ADMIN_BOT_TOKEN`
- `MARKET_API_BASE`
- `MARKET_ADMIN_MINI_APP_URL`
- `MARKET_SUPPORT_LINK`
- `MARKET_INTERNAL_API_SECRET` (должен совпадать с backend)

### `superadmin_bot`

- `MARKET_SUPERADMIN_BOT_TOKEN`
- `MARKET_API_BASE`
- `MARKET_SUPERADMIN_ALLOWED_IDS` (опционально)
- `MARKET_SUPERADMIN_MINI_APP_URL`
- `MARKET_SUPPORT_LINK`

## Что делает каждый бот

- `user_bot`: онбординг клиента, запрос контакта, открытие клиентского Mini App, запрос статуса заказа.
- `admin_bot`: быстрый вход в admin Mini App, сервисные действия по заказам.
- `superadmin_bot`: команды мониторинга (`/health`, `/stats`) и выборка сущностей (`/order`, `/restaurant`, `/user`).

## Проверка работоспособности

1. Запустить backend (`backend/BACKEND_README.md`).
2. Запустить нужного бота.
3. Отправить `/start` соответствующему боту в Telegram.
4. Проверить логи бота и ответы API.
