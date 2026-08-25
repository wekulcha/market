# Kulcha Market Platform

Платформа приема заказов для маркета с Telegram-интеграцией:

- клиентский `user_panel` (Mini App);
- `admin_panel` для персонала ресторана (Mini App);
- `superadmin_panel` для управления платформой;
- `backend` на FastAPI;
- 3 Telegram-бота в `bots/`.

## Актуальная структура

- `backend/` — основной API-сервер (FastAPI + SQLAlchemy async + Alembic)
- `user_panel/` — клиентский интерфейс заказа
- `admin_panel/` — панель магазина (заказы, товары, аналитика)
- `superadmin_panel/` — панель суперадмина
- `bots/` — `user_bot`, `admin_bot`, `superadmin_bot`
- `deploy/` — Dockerfiles, Caddy gateway, скрипты
- `scripts/` — утилиты эксплуатации и миграций

## Быстрый старт (локально)

### 1) Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Проверка: `http://localhost:8000/health`

### 2) Frontend-панели

```bash
cd user_panel && npm install && npm run dev
cd admin_panel && npm install && npm run dev
cd superadmin_panel && npm install && npm run dev
```

Для панелей используется `VITE_API_URL` (обычно `http://localhost:8000/api/v1` локально или `PUBLIC_API_URL` в docker-сборке).

### 3) Telegram-боты

```bash
cd bots/user_bot && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt && python main.py
cd bots/admin_bot && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt && python main.py
cd bots/superadmin_bot && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt && python main.py
```

Ссылка на поддержку в маркетовых ботах ведет на общий support bot Kulcha через `MARKET_SUPPORT_LINK`.

## Запуск в Docker Compose

```bash
docker compose up -d
```

Сервисы поднимутся по `docker-compose.yml`: PostgreSQL, backend, 3 панели, 3 бота и Caddy gateway.

## Документация по модулям

- `backend/BACKEND_README.md` — API, переменные окружения, миграции.
- `bots/BOTS_README.md` — запуск и конфиги всех ботов.
- `user_panel/USER_PANEL_README.md` — клиентский Mini App.
- `admin_panel/ADMIN_PANEL_README.md` — панель ресторана.
- `superadmin_panel/SUPERADMIN_PANEL_README.md` — панель суперадмина.
- `scripts/SCRIPTS_README.md` — утилиты и env для dev/ops.
- `THESIS_README.md` — материал для подготовки ВКР.
