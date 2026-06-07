# Kulcha Market Scripts (`scripts`)

Каталог эксплуатационных и вспомогательных скриптов проекта.

## Что находится в каталоге

- `market-dev.env.example` — пример env-набора для локальной разработки.
- `migrate_uploads_to_object_storage.py` — перенос локальных файлов в object storage.
- прочие утилиты, применяемые в dev/ops-процессах.

## Работа с переменными окружения

1. Возьмите за основу `market-dev.env.example`.
2. Создайте локальную копию с секретами (например, `market-dev.env`).
3. Не коммитьте файлы с реальными секретами.

Ключевые группы переменных:

- база данных (`MARKET_DATABASE_URL`, `MARKET_POSTGRES_*`);
- токены ботов (`MARKET_*_BOT_TOKEN`);
- внутренние секреты (`MARKET_INTERNAL_API_SECRET`, `MARKET_BOT_API_SECRET`);
- object storage (`MARKET_OBJECT_STORAGE_*`);
- домены и публичные URL (`MARKET_*_DOMAIN`, `MARKET_PUBLIC_API_URL`, `MARKET_CORS_ALLOWED_ORIGINS`).

Подробности по запуску backend и ботов см. в:

- `backend/BACKEND_README.md`
- `bots/BOTS_README.md`
