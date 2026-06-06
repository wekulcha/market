# KULCHA User Panel (`user_panel`)

Клиентское приложение заказа еды (Telegram Mini App).

## Функциональность

- просмотр списка ресторанов;
- просмотр меню выбранного ресторана;
- корзина и checkout;
- профиль пользователя;
- история заказов.

## Технологии

- React 19
- TypeScript
- Vite 7
- React Router 7
- TanStack Query 5
- Tailwind CSS 4

## Запуск локально

```bash
cd user_panel
npm install
npm run dev
```

Дополнительно:

```bash
npm run lint
npm run build
npm run preview
```

## Переменные окружения

- `VITE_API_URL` — базовый URL backend API, например `http://localhost:8000/api/v1`

Если переменная не задана, приложение использует значение из локальной конфигурации проекта.

## Маршруты (основные)

- `/` — стартовый экран
- `/cafes` — список ресторанов
- `/cafes/:restaurantId/menu` — меню ресторана
- `/cart` — корзина
- `/checkout` — оформление заказа
- `/profile` — профиль
- `/orders/history` — история заказов

## Интеграция с Telegram

Приложение рассчитано на запуск как Mini App из `user_bot`.  
Для корректной работы внутри Telegram в продакшене нужен HTTPS-домен.
