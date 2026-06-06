# KULCHA Superadmin Panel (`superadmin_panel`)

Панель управления платформой KULCHA.

## Функциональность

- управление ресторанами;
- просмотр и анализ заказов;
- просмотр пользователей;
- раздел аналитики;
- технические инструменты платформы.

## Технологии

- React 19
- TypeScript
- Vite 8
- React Router 7
- TanStack Query 5
- Tailwind CSS 3

## Запуск локально

```bash
cd superadmin_panel
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

## Маршруты (основные)

- `/` — рестораны
- `/users` — пользователи
- `/orders` — заказы
- `/analytics` — аналитика
- `/tools` — служебные инструменты

## Интеграция

- backend API: `backend/`
- вход через Telegram WebApp flow (используется в паре с `superadmin_bot`)
