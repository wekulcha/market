# KULCHA B2B

KULCHA B2B — добавочный Telegram-first контур внутри `market/`. Он использует
единый FastAPI backend и PostgreSQL, но не меняет команды запуска legacy Market.

## Runtime-карта

| Сервис | Compose service | Назначение |
|---|---|---|
| API | `backend` | Общий FastAPI API, auth, B2B domain и webhooks |
| Web | `b2b_panel` | Одна SPA с маршрутами `/buyer`, `/seller`, `/admin` |
| Buyer bot | `buyer_bot` | Invite, contact, каталог, заказы, подписка |
| Seller bot | `seller_bot` | Contact, предложения, заказы поставщика |
| Admin bot | `b2b_admin_bot` | Allowlisted alerts и quick actions с подтверждением |
| Worker | `notification_worker` | PostgreSQL outbox, retry и истечение резервов |
| Redis | `redis` | Buyer FSM и дедупликация Telegram updates в webhook mode |
| Edge | `gateway` | HTTPS и path routing; legacy host routes сохраняются |

Все новые runtime-сервисы помечены profile `b2b`. Обычный
`docker compose up -d` продолжает поднимать legacy Market без них.

## Важное уведомление о секретах

Аудит обнаружил ранее закоммиченные Telegram bot tokens в legacy `.env` и
dev-env файлах. Значения намеренно не приводятся. Считать их скомпрометированными,
немедленно отозвать через BotFather, выпустить новые и выполнить согласованную
очистку Git history. Новый `.gitignore` не удаляет уже tracked файлы и не заменяет
rotation. Полный runbook: [`docs/security.md`](docs/security.md).

## Требования

- Docker Engine с Compose v2;
- три отдельных Telegram-бота от BotFather;
- HTTPS URL для запуска Mini Apps из Telegram;
- Python 3.12 и Node 20 — только для запуска без Docker.

## 1. Настройка окружения

Никогда не перезаписывайте существующий `.env`. Если файла ещё нет:

```bash
cp .env.example .env
```

Сгенерируйте независимые секреты. Команды только печатают новые значения; внесите
их в локальный `.env` вручную и не копируйте вывод в тикеты/логи:

```bash
for name in B2B_INTERNAL_API_SECRET BUYER_BOT_WEBHOOK_SECRET SELLER_BOT_WEBHOOK_SECRET ADMIN_BOT_WEBHOOK_SECRET; do
  printf '%s=' "$name"
  python -c 'import secrets; print(secrets.token_urlsafe(48))'
done
```

Минимально заполните:

```dotenv
APP_ENV=development
PUBLIC_BASE_URL=https://your-public-dev-domain.example
B2B_DOMAIN=your-public-dev-domain.example
# Host-only refresh cookie is required outside wekulcha.ru.
MARKET_AUTH_COOKIE_DOMAIN=
# Keep true for an HTTPS tunnel; use false only on plain HTTP localhost.
MARKET_AUTH_COOKIE_SECURE=true
BUYER_BOT_TOKEN=
BUYER_BOT_USERNAME=
BUYER_BOT_MODE=polling
SELLER_BOT_TOKEN=
SELLER_BOT_USERNAME=
SELLER_BOT_MODE=polling
ADMIN_BOT_TOKEN=
ADMIN_BOT_USERNAME=
ADMIN_BOT_MODE=polling
ADMIN_TELEGRAM_IDS=
B2B_INTERNAL_API_SECRET=
B2B_BOOTSTRAP_SUPERADMIN_TELEGRAM_ID=
DELIVERY_PROVIDER=manual
```

`ADMIN_TELEGRAM_IDS` — comma-separated Telegram user IDs. Пустой список означает
fail-closed: `b2b_admin_bot` завершится с ошибкой конфигурации. Bootstrap ID должен
также входить в этот список.

Пустой `MARKET_AUTH_COOKIE_DOMAIN` создаёт host-only refresh cookie для localhost
или tunnel вне `wekulcha.ru`. Compose сохраняет legacy default `.wekulcha.ru`, если
переменная отсутствует, поэтому именно пустое значение должно присутствовать в
local `.env`. Для HTTPS tunnel оставьте `MARKET_AUTH_COOKIE_SECURE=true`; `false`
допустим только для plain `http://localhost`. В production используйте
`MARKET_AUTH_COOKIE_DOMAIN=.wekulcha.ru` и `MARKET_AUTH_COOKIE_SECURE=true`.

Для local/dev оставьте три `*_BOT_MODE=polling`. Для production используйте
`webhook`, HTTPS `PUBLIC_BASE_URL`, три независимых секрета длиной не менее 32:

```dotenv
BUYER_BOT_MODE=webhook
SELLER_BOT_MODE=webhook
ADMIN_BOT_MODE=webhook
BUYER_BOT_WEBHOOK_SECRET=
SELLER_BOT_WEBHOOK_SECRET=
ADMIN_BOT_WEBHOOK_SECRET=
REDIS_URL=rediss://user:password@managed-redis.example/0
```

На старте bot сам вызывает Telegram `setWebhook`. Aiogram проверяет secret header
до dispatch. Все три bot-а отказываются стартовать в webhook mode без Redis:
обработчик отвечает Telegram только после завершения dispatch и хранит обработанный
`update_id` семь суток. Redis lock не позволяет параллельным delivery одного update
получить преждевременный `200`. Buyer дополнительно хранит invite/contact FSM в
Redis, поэтому состояние переживает рестарт. В local Compose доступен непубличный
`redis` service, а в production нужен аутентифицированный/TLS Redis либо
эквивалентный managed service.

`DELIVERY_PROVIDER=manual` — безопасный MVP default: администратор назначает
курьера и меняет этапы доставки вручную. Новый внешний провайдер подключается через
backend provider adapter; не переключайте значение до реализации contract tests,
проверки подписи/idempotency webhook и согласованного rollback.

Полный перечень B2B-переменных находится в `.env.example`. Compose явно переводит
master-compatible имена в `MARKET_B2B_*`, которые читает backend.

## 2. Миграции и local seed

Сначала поднимите PostgreSQL и backend, затем примените Alembic. Простого
`docker compose up` недостаточно для чистой базы.

```bash
docker compose up -d --build postgres backend
docker compose exec -T backend alembic upgrade head
```

Backend не публикует порт в root Compose. В Docker проверяйте health так:

```bash
docker compose exec -T backend python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
```

Local seed создаёт roles, bootstrap superadmin mapping, demo plan/categories,
seller, offer и buyer invite. Он отказывается работать с не-local DB без явного
override и печатает raw invite token только в local/dev:

```bash
docker compose run --rm \
  --volume "$PWD:/workspace" \
  --workdir /workspace \
  backend python scripts/seed_b2b_local.py
```

Не сохраняйте напечатанный invite token в Git или общих логах. Buyer deep link:

```text
https://t.me/<BUYER_BOT_USERNAME>?start=invite_<TOKEN>
```

## 3. Запуск

Весь контур:

```bash
docker compose --profile b2b up -d --build
docker compose --profile b2b ps
docker compose logs --tail=100 backend notification_worker buyer_bot seller_bot b2b_admin_bot
```

UI/API/worker без Telegram-ботов (полезно до получения BotFather tokens):

```bash
docker compose --profile b2b up -d --build postgres backend b2b_panel notification_worker gateway
```

Остановка без удаления PostgreSQL volume:

```bash
docker compose --profile b2b stop \
  b2b_panel buyer_bot seller_bot b2b_admin_bot notification_worker redis
```

`docker compose --profile b2b down` остановит также legacy Market. Не добавляйте
`--volumes`, если удаление local data не является явной целью.

## 4. Local frontend без публичного gateway

```bash
cd b2b_panel
npm install
npm run dev
```

Vite работает на `http://localhost:5176` и проксирует `/api` на backend
`127.0.0.1:8000`. Для настоящего Telegram Mini App нужен HTTPS tunnel; после его
создания обновите `PUBLIC_BASE_URL` и BotFather Web App URLs.

Production bundles используют отдельный asset namespace `/b2b-static/`, чтобы
не конфликтовать с legacy `/assets` на `app.wekulcha.ru`.

## 5. Маршруты

- `${PUBLIC_BASE_URL}/buyer` — buyer Mini App;
- `${PUBLIC_BASE_URL}/seller` — seller Mini App;
- `${PUBLIC_BASE_URL}/admin` — admin web;
- `${PUBLIC_BASE_URL}/api/...` — backend без strip-prefix;
- `${PUBLIC_BASE_URL}/{health|ready|metrics}` — backend operations endpoints;
- `${PUBLIC_BASE_URL}/webhooks/telegram/{buyer|seller|admin}` — напрямую в соответствующий bot;
- `${PUBLIC_BASE_URL}/webhooks/payments/{provider}` — payment webhook.

Caddy обрабатывает `/api` и все `/webhooks` до SPA fallback; точные Telegram
маршруты идут в соответствующие bot containers, payment webhook — в backend. При
shared gateway нужно
вручную merge handlers из `deploy/shared-gateway.Caddyfile.example` в уже
существующий `app.wekulcha.ru` block и подключить gateway к network:

```bash
docker network connect kulcha-market_default kulcha-gateway
docker exec kulcha-gateway caddy reload --config /etc/caddy/Caddyfile
```

Повторный `docker network connect` может вернуть «already exists» — это нормально.
Перед reload обязательно выполните Caddy validation из production checklist.

## 6. Telegram bot команды

Buyer bot:

- `/start invite_<TOKEN>`;
- `/catalog`;
- `/orders`;
- `/subscription`;
- `/support`.

Seller bot:

- `/start`;
- `/offers`;
- `/new_offer`;
- `/orders`;
- `/support`.

Admin bot:

- `/start`;
- `/dashboard`;
- `/offers`;
- `/orders`;
- `/support`.

В polling mode buyer invite хранится в process-memory FSM только до отправки
contact; после рестарта покупатель повторно открывает ту же deep link. В webhook
mode FSM хранится в Redis. В обоих режимах backend остаётся источником истины и
защищает token от повторного использования.

Compose поддерживает `polling` (local default) и `webhook` (production). Polling
снимает старый webhook; webhook mode слушает внутренние порты 8081/8082/8083, а
Caddy терминирует HTTPS. Все webhook adapters используют Redis для dedup/lock по
`update_id`; buyer также использует RedisStorage для FSM. Никогда не запускайте два
consumer-а одного token.

## 7. E2E smoke flow

1. Применить миграции и выполнить `scripts/seed_b2b_local.py`.
2. Войти bootstrap superadmin в `/admin` и проверить role.
3. Открыть seller bot, `/start`, отправить только собственный Telegram contact.
4. В `/seller` заполнить профиль, создать offer с фото и отправить на модерацию.
5. Убедиться, что admin bot получил alert; открыть offer, назначить markup и publish.
6. Открыть seed buyer invite, отправить собственный contact, активировать dev plan.
7. В `/buyer` открыть catalog, добавить допустимое количество и оформить order.
8. Проверить reserve; seller подтверждает наличие и готовность.
9. Admin назначает delivery и проводит order до `DELIVERED/COMPLETED`.
10. Проверить quantity, price snapshots, margin, audit log и notification outbox.

После smoke запустите backend tests и frontend tests; не фиксируйте результат как
успешный, если команда не была выполнена:

```bash
cd backend && pytest -q
cd ../b2b_panel && npm test -- --run && npm run build
```

Автоматизированный destructive smoke создаёт новый offer, проводит его через
модерацию/наценку/publication, активирует buyer, делает idempotent checkout,
seller confirmation, delivery и `COMPLETED`. Только для disposable local/staging:

```bash
docker compose run --rm --no-deps \
  --volume "$PWD:/workspace:ro" \
  --workdir /workspace \
  --env B2B_E2E_BASE_URL=http://kulcha-market-backend:8000 \
  --env B2B_E2E_ALLOW_MUTATIONS=1 \
  backend python scripts/b2b_e2e_smoke.py
```

До команды должны быть выполнены migration + seed, запущен основной `backend`, а
в `.env` заданы все три bot token/username, admin/bootstrap IDs, auth/internal
secrets. Скрипт не печатает invite/JWT/token и отказывается от remote target без
дополнительного `B2B_E2E_ALLOW_REMOTE=1`. Не включайте это для production.

Нагрузочный catalog+checkout сценарий лежит в `scripts/load/b2b_locustfile.py`.
Используйте только отдельный staging и по одной уникальной buyer credential на VU:

```bash
python -m venv .load/venv
source .load/venv/bin/activate
pip install -r scripts/load/requirements.txt
B2B_LOAD_BUYER_CREDENTIALS_FILE=/secure/path/b2b-load-buyers.json \
B2B_LOAD_ENABLE_CHECKOUT=1 \
B2B_LOAD_ALLOW_MUTATIONS=1 \
B2B_LOAD_CANCEL_ORDERS=1 \
locust -f scripts/load/b2b_locustfile.py \
  --headless --users 10 --spawn-rate 2 --run-time 2m \
  --host https://b2b-staging.example
```

Файл — JSON array с `accessToken`, `addressId`, `offerId`, `quantity`,
`recipientName`, `recipientPhone`; храните его вне репозитория. Отмена возвращает
остаток, но строки заказов/audit остаются, поэтому staging DB всё равно disposable.
Для release baseline повторите отдельные изолированные прогоны на 50, 100 и 300 VU,
выдав не меньше одного уникального buyer credential на каждый VU и достаточный
stock. Записывайте только фактические latency/error/throughput из реально выполненных
прогонов; этот репозиторий не заявляет выдуманных результатов.

## 8. Эксплуатация

- ADR: [`docs/adr/0001-b2b-runtime.md`](docs/adr/0001-b2b-runtime.md)
- операции и monitoring: [`docs/operations.md`](docs/operations.md)
- security/secret incident: [`docs/security.md`](docs/security.md)
- backup/restore: [`docs/backup-restore.md`](docs/backup-restore.md)
- rollback: [`docs/rollback.md`](docs/rollback.md)
- production checklist: [`docs/production-checklist.md`](docs/production-checklist.md)
