# KULCHA Admin Panel (`admin_panel`)

Панель персонала ресторана (Telegram Mini App).

## Функциональность

- список ресторанов, доступных текущему сотруднику;
- обработка заказов (просмотр и смена статусов);
- управление меню (CRUD блюд);
- базовая аналитика по заказам.

## Технологии

- React 18
- TypeScript
- Vite 7
- React Router 6
- TanStack Query 5
- Tailwind CSS 3

## Запуск локально

```bash
cd admin_panel
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

## Маршруты

- `/` — список ресторанов сотрудника
- `/restaurants/:id` — страница ресторана (заказы, меню, аналитика)
- `/profile` — профиль

## Интеграция

- backend API: `backend/`
- Telegram вход: через `admin_bot`

Для корректной работы как Mini App в продакшене должен использоваться HTTPS.
