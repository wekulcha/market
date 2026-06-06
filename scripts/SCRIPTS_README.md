# KULCHA Scripts (`scripts`)

Каталог эксплуатационных и вспомогательных скриптов проекта.

## Что находится в каталоге

- `kulcha-dev.env.example` — пример env-набора для локальной разработки.
- `migrate_uploads_to_object_storage.py` — перенос локальных файлов в object storage.
- прочие утилиты, применяемые в dev/ops-процессах.

## Работа с переменными окружения

1. Возьмите за основу `kulcha-dev.env.example`.
2. Создайте локальную копию с секретами (например, `kulcha-dev.env`).
3. Не коммитьте файлы с реальными секретами.

Ключевые группы переменных:

- база данных (`KULCHA_DATABASE_URL`, `POSTGRES_*`);
- токены ботов (`KULCHA_*_BOT_TOKEN`);
- внутренние секреты (`KULCHA_INTERNAL_API_SECRET`, `KULCHA_BOT_API_SECRET`);
- object storage (`KULCHA_OBJECT_STORAGE_*`);
- домены и публичные URL (`API_DOMAIN`, `PUBLIC_API_URL`, `KULCHA_CORS_ALLOWED_ORIGINS`).

Подробности по запуску backend и ботов см. в:

- `backend/BACKEND_README.md`
- `bots/BOTS_README.md`
