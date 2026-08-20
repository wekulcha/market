# KULCHA B2B Panel

Самостоятельная React + TypeScript SPA для трёх изолированных интерфейсов KULCHA B2B. Legacy `user_panel`, `admin_panel` и `superadmin_panel` не используются и не изменяются.

## Маршруты

- `/buyer/*` — mobile-first кабинет покупателя;
- `/seller/*` — mobile-first кабинет поставщика;
- `/admin/*` — desktop-first адаптивная админ-панель;
- `/api/*` — единый backend, задаётся через `VITE_API_URL`;
- `/b2b-static/*` — отдельный namespace production assets, чтобы не конфликтовать с legacy SPA.

React routes не используют basename: `VITE_ASSET_BASE_URL` влияет только на URL собранных JS/CSS/assets. Внешний gateway обязан отдавать один и тот же `index.html` при прямом открытии вложенных `/buyer/...`, `/seller/...` и `/admin/...`.

## Возможности

- Telegram `initData` login, in-memory bearer token, secure refresh cookie и single-flight retry после 401;
- role guards для `BUYER`, `SELLER`, `ADMIN`, `SUPERADMIN`;
- buyer subscription policy (`BLOCKED`, `TEASER`, `READ_ONLY`, `FULL`), каталог, server cart, quantity minimum/step, checkout с idempotency key, заказы и профиль;
- seller verification, черновики и повторная отправка предложений, несколько изображений, статусы модерации, подтверждение и готовность заказа;
- admin KPI dashboard, модерация/наценка/публикация, buyers/sellers/subscriptions/orders/delivery/invites/notifications/audit/settings;
- Telegram theme variables, CSS design tokens, safe-area insets, loading/empty/error states и reduced-motion support.

Buyer API использует отдельный `BuyerOffer`: в типе отсутствуют закупочная цена, supplier id/name/contact, pickup address и внутренние комментарии. Все wire-суммы — целые значения в копейках с суффиксом `*Kopecks`; преобразование в рубли выполняется только форматтером UI.

## Переменные окружения

```dotenv
VITE_API_URL=/api
VITE_ASSET_BASE_URL=/b2b-static/
VITE_APP_NAME=KULCHA B2B
```

Для локальной разработки Vite проксирует `/api` на `http://127.0.0.1:8000`.

## Запуск и проверка

```bash
cd market/b2b_panel
npm ci
npm run dev
npm run test
npm run typecheck
npm run build
```

Dev server: `http://localhost:5176/buyer` (также `/seller` и `/admin`). Production build создаётся в `dist/`; deployment/gateway находятся за пределами этого каталога.

## API contract

- `POST /api/auth/telegram` — `{ initDataRaw, role }`;
- `POST /api/auth/refresh` — refresh cookie;
- `/api/buyer/*`, `/api/seller/*`, `/api/admin/*` — role-isolated endpoints;
- subscription payment и order creation отправляют одинаковый `idempotencyKey` в body и `Idempotency-Key` header;
- mutation permissions, privacy, price/stock recalculation, reservation and state transitions проверяются backend, а не frontend.

## Тесты

Vitest покрывает role/subscription guards, дробные minimum/step quantity rules и smoke routing всех трёх пространств.
