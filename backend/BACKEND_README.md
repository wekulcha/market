# KULCHA Backend (`backend`)

Основной API-сервер платформы: FastAPI + SQLAlchemy async + Alembic + PostgreSQL.

## Технологии

- FastAPI
- SQLAlchemy (async) + asyncpg
- Alembic
- pydantic-settings
- httpx
- boto3 (S3-compatible object storage)

## Локальный запуск

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Проверки:

- Health: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

## Основные API-префиксы

Все endpoints находятся под `/api/v1`.

- `/auth`
- `/users`
- `/restaurants`
- `/meals`
- `/meal-assets`, `/restaurant-assets`
- `/orders`, `/order-positions`
- `/staff`, `/restaurants/{restaurant_id}/staff`
- `/couriers`, `/courier-panel`
- `/subscription-logs`
- `/admin`
- `/internal/support`

## Переменные окружения (ключевые)

| Переменная | Обязательно | Значение по умолчанию | Назначение |
|---|---|---|---|
| `MARKET_DATABASE_URL` | Да | `postgresql+asyncpg://kulcha_market:kulcha_market@localhost:5433/kulcha_market` | Подключение к PostgreSQL |
| `MARKET_USER_BOT_TOKEN` | Да | — | Токен user_bot |
| `MARKET_ADMIN_BOT_TOKEN` | Да | — | Токен admin_bot |
| `MARKET_SUPERADMIN_BOT_TOKEN` | Для superadmin auth | — | Токен superadmin_bot |
| `MARKET_SUPERADMIN_ALLOWED_IDS` | Нет | — | Список разрешенных Telegram ID |
| `MARKET_INTERNAL_API_SECRET` | Да | — | Внутренний секрет backend <-> боты |
| `MARKET_BOT_API_SECRET` | Нет | — | Дополнительный секрет bot API |
| `MARKET_AUTH_ACCESS_SECRET` | Да | — | Секрет access-токена |
| `MARKET_AUTH_ACCESS_TTL_MINUTES` | Нет | `15` | TTL access |
| `MARKET_AUTH_REFRESH_TTL_DAYS` | Нет | `30` | TTL refresh |
| `MARKET_AUTH_COOKIE_DOMAIN` | Нет | — | Домен auth-cookie |
| `MARKET_AUTH_COOKIE_SECURE` | Нет | `true` | Secure cookie |
| `MARKET_OBJECT_STORAGE_ENDPOINT` | Нет | `https://storage.yandexcloud.net` | Endpoint object storage |
| `MARKET_OBJECT_STORAGE_REGION` | Нет | `ru-central1` | Регион object storage |
| `MARKET_OBJECT_STORAGE_BUCKET` | Нет | `kulcha-market-menu-items` | Bucket |
| `MARKET_OBJECT_STORAGE_ACCESS_KEY_ID` | Для upload | — | Access key |
| `MARKET_OBJECT_STORAGE_SECRET_ACCESS_KEY` | Для upload | — | Secret key |
| `MARKET_OBJECT_STORAGE_PUBLIC_BASE_URL` | Нет | `https://kulcha-market-menu-items.storage.yandexcloud.net` | Публичный URL файлов |
| `MARKET_CORS_ALLOWED_ORIGINS` | Нет | — | Основной список CORS origins |
| `MARKET_CORS_ADDITIONAL_ORIGINS` | Нет | — | Доп. CORS origins |

## Миграции базы данных

```bash
cd backend
source venv/bin/activate

# Применить миграции
alembic upgrade head

# Создать новую миграцию
alembic revision --autogenerate -m "describe_change"
```

## Запуск в Docker

Из корня проекта:

```bash
docker compose up -d postgres backend
```
