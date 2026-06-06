# KULCHA Telegram Mini-App - Project Structure

This document provides a comprehensive overview of the project structure, including all source files, configuration files, and their purposes.

## 📁 Complete Project Tree

```
user_panel/
├── dist/                           # Build output directory (generated)
│   ├── assets/
│   │   ├── index-*.js             # Compiled JavaScript bundle
│   │   └── index-*.css            # Compiled CSS bundle
│   ├── index.html                 # Compiled HTML
│   └── vite.svg                   # Static asset
│
├── node_modules/                   # Dependencies (generated, not tracked)
│
├── public/                         # Static assets
│   └── vite.svg                    # Vite logo
│
├── src/                            # Source code
│   ├── api/                        # API client layer
│   │   ├── baseUrl.ts             # Base URL configuration
│   │   ├── meals.ts               # Meals API client
│   │   ├── orders.ts              # Orders API client
│   │   └── restaurants.ts         # Restaurants API client
│   │
│   ├── assets/                     # Static assets
│   │   └── react.svg              # React logo
│   │
│   ├── components/                # Reusable components
│   │   ├── cart/
│   │   │   └── CartItemRow.tsx   # Cart item row component
│   │   └── menu/
│   │       └── MenuItemCard.tsx   # Menu item card component
│   │
│   ├── context/                    # React Context providers
│   │   ├── AppContext.tsx         # Global app state
│   │   └── CartContext.tsx        # Shopping cart state
│   │
│   ├── layout/                     # Layout components
│   │   ├── BottomBarCart.tsx      # Bottom cart bar
│   │   ├── Header.tsx             # Page header
│   │   └── MiniAppShell.tsx      # Main layout wrapper
│   │
│   ├── pages/                      # Page components
│   │   ├── CafeList/
│   │   │   └── CafeListPage.tsx   # Restaurant list page
│   │   ├── Cart/
│   │   │   └── CartPage.tsx      # Shopping cart page
│   │   ├── Checkout/
│   │   │   └── CheckoutPage.tsx   # Checkout page
│   │   ├── Menu/
│   │   │   └── MenuPage.tsx      # Menu page
│   │   ├── Profile/
│   │   │   └── ProfilePage.tsx   # User profile page
│   │   └── Splash/
│   │       └── SplashPage.tsx     # Welcome/splash page
│   │
│   ├── telegram/                   # Telegram integration
│   │   └── initTelegram.ts        # Telegram WebApp init
│   │
│   ├── types/                      # TypeScript type definitions
│   │   ├── cart.ts                # Cart types
│   │   ├── meal.ts               # Meal types
│   │   ├── order.ts              # Order types
│   │   ├── restaurant.ts         # Restaurant types
│   │   └── user.ts               # User types
│   │
│   ├── App.tsx                    # Root component
│   ├── index.css                  # Global styles
│   ├── main.tsx                   # Application entry point
│   └── router.tsx                 # React Router configuration
│
├── .gitignore                      # Git ignore rules
├── eslint.config.js               # ESLint configuration
├── index.html                      # HTML entry point
├── package.json                    # NPM package configuration
├── package-lock.json               # NPM lock file
├── postcss.config.js               # PostCSS configuration
├── PROJECT_STRUCTURE.md            # This file
├── USER_PANEL_README.md            # Project readme
├── tailwind.config.js              # TailwindCSS configuration
├── tsconfig.json                   # TypeScript configuration (base)
├── tsconfig.app.json               # TypeScript configuration (app)
├── tsconfig.node.json              # TypeScript configuration (node)
└── vite.config.ts                  # Vite build configuration
```

## 📁 Root Directory Files

---

## 📂 Source Code (`src/`)

### Entry Points

- **`src/main.tsx`**
  - React application entry point
  - Initializes Telegram WebApp
  - Renders App component in StrictMode

- **`src/App.tsx`**
  - Root component
  - Wraps application with context providers (AppContext, CartContext)
  - Provides RouterProvider

- **`src/router.tsx`**
  - React Router configuration
  - Defines all application routes

---

## 📂 API Layer (`src/api/`)

### Base Configuration

- **`src/api/baseUrl.ts`**
  - Centralized API base URL configuration
  - Exports `BASE_URL` constant

### API Clients

- **`src/api/restaurants.ts`**
  - `fetchRestaurants()` - Fetches list of all restaurants
  - GET `/api/restaurants`

- **`src/api/meals.ts`**
  - `fetchMealsByRestaurant(restaurantId)` - Fetches meals for a restaurant
  - GET `/api/restaurants/:id/meals`
  - Filters out unavailable meals

- **`src/api/orders.ts`**
  - `createOrder(payload)` - Creates a new order
  - POST `/api/orders`
  - Returns order response with ID and total

---

## 📂 Types (`src/types/`)

- **`src/types/restaurant.ts`**
  - `Restaurant` interface
  - Fields: id, name, address

- **`src/types/meal.ts`**
  - `Meal` interface
  - Fields: id, restaurant_id, name, description, weight, calorie, image_link, category, price, is_available

- **`src/types/user.ts`**
  - `User` interface
  - Fields: id (telegram_id), username, phone, email, address, registered_at

- **`src/types/cart.ts`**
  - `CartItem` interface (meal + quantity)
  - `CartState` interface

- **`src/types/order.ts`**
  - `PaymentMethod` type ('CASH' | 'TRANSFER')
  - `OrderItemPayload` interface
  - `CreateOrderPayload` interface
  - `OrderResponse` interface

---

## 📂 Context (`src/context/`)

- **`src/context/AppContext.tsx`**
  - Global application state
  - Manages: `serviceType` ('DELIVERY' | 'DINE_IN'), `selectedRestaurant`
  - Exports: `AppContextProvider`, `useAppContext()`

- **`src/context/CartContext.tsx`**
  - Shopping cart state management
  - Manages: `items`, `totalItems`
  - Methods: `addItem()`, `increment()`, `decrement()`, `getItemQuantity()`
  - Exports: `CartContextProvider`, `useCart()`

---

## 📂 Layout Components (`src/layout/`)

- **`src/layout/MiniAppShell.tsx`**
  - Main layout wrapper
  - Emulates mobile viewport (max-width 430px)
  - Centers content, provides padding and background
  - Accepts `children` prop

- **`src/layout/Header.tsx`**
  - Reusable header component
  - Props: `title`, `onBurgerClick`, `onSearchClick`, `showSearch`
  - Contains: burger menu button, title, search button
  - Used across all pages

- **`src/layout/BottomBarCart.tsx`**
  - Sticky bottom cart bar
  - Shows cart icon with item count badge
  - Displays "Корзина" or "Продолжить" based on cart state
  - Navigates to `/cart` when clicked (if items exist)

---

## 📂 Pages (`src/pages/`)

### Splash Page

- **`src/pages/Splash/SplashPage.tsx`**
  - Route: `/`
  - Welcome screen with KULCHA logo
  - Auto-navigates to `/cafes` after 1.3 seconds

### Cafe List Page

- **`src/pages/CafeList/CafeListPage.tsx`**
  - Route: `/cafes`
  - Displays grid of restaurants
  - Service type toggle (Доставка/В зале)
  - Search functionality (filters by name/address)
  - Clicking restaurant navigates to menu page

### Menu Page

- **`src/pages/Menu/MenuPage.tsx`**
  - Route: `/cafes/:restaurantId/menu`
  - Displays meals grouped by category
  - Sticky category tabs with auto-highlight on scroll
  - Search functionality (filters by name/description)
  - Service type toggle
  - Renders MenuItemCard components

### Cart Page

- **`src/pages/Cart/CartPage.tsx`**
  - Route: `/cart`
  - Displays cart items with CartItemRow components
  - Shows service type information
  - Calculates and displays total
  - "ДАЛЕЕ" button navigates to checkout

### Checkout Page

- **`src/pages/Checkout/CheckoutPage.tsx`**
  - Route: `/checkout`
  - Order form with:
    - Restaurant summary
    - Delivery address (floor/line/pavilion) for DELIVERY
    - Contact information (username, phone)
    - Payment method selection
    - Order summary (items, delivery fee, service fee, total)
  - "ЗАКАЗАТЬ" button submits order
  - Handles loading, error, and success states

### Profile Page

- **`src/pages/Profile/ProfilePage.tsx`**
  - Route: `/profile`
  - User profile information
  - Mock user data display
  - Placeholders for current order and order history
  - Legal links (Privacy Policy, Terms of Service)

---

## 📂 Components (`src/components/`)

### Menu Components

- **`src/components/menu/MenuItemCard.tsx`**
  - Displays individual meal card
  - Shows: image, name, description, weight, price
  - Quantity controls (+ / - buttons)
  - Integrates with CartContext

### Cart Components

- **`src/components/cart/CartItemRow.tsx`**
  - Displays cart item in cart page
  - Shows: image, name, price per unit, weight, position total
  - Quantity controls with increment/decrement
  - Integrates with CartContext

---

## 📂 Telegram Integration (`src/telegram/`)

- **`src/telegram/initTelegram.ts`**
  - Initializes Telegram WebApp
  - Checks for `window.Telegram.WebApp`
  - Calls `WebApp.ready()`
  - Sets theme-related CSS variables
  - Graceful fallback when not in Telegram

---

## 📂 Styles (`src/`)

- **`src/index.css`**
  - Global styles
  - TailwindCSS imports
  - Custom utilities (line-clamp-2, scrollbar-hide)
  - Base body styles

---

## 📂 Assets (`src/assets/`)

- **`src/assets/react.svg`**
  - React logo (default Vite asset)

---

## ⚙️ Configuration Files

### Build Configuration

- **`vite.config.ts`**
  - Vite build tool configuration
  - React plugin setup

- **`tsconfig.json`**
  - Base TypeScript configuration
  - Compiler options

- **`tsconfig.app.json`**
  - TypeScript configuration for application code
  - Extends base config

- **`tsconfig.node.json`**
  - TypeScript configuration for Node.js scripts
  - Used for Vite config and build scripts

### Styling Configuration

- **`tailwind.config.js`**
  - TailwindCSS configuration
  - Content paths
  - Theme customization

- **`postcss.config.js`**
  - PostCSS configuration
  - TailwindCSS plugin
  - Autoprefixer plugin

### Code Quality

- **`eslint.config.js`**
  - ESLint configuration
  - React hooks rules
  - TypeScript rules

### Package Management

- **`package.json`**
  - NPM package configuration
  - Dependencies and devDependencies
  - Scripts: dev, build, lint, preview

---

## 📂 Public Assets (`public/`)

- **`public/vite.svg`**
  - Vite logo (default asset)

---

## 📂 Build Output (`dist/`)

Generated during build process:
- **`dist/index.html`** - Compiled HTML
- **`dist/assets/`** - Compiled JS and CSS bundles

---

## 🗂️ File Organization Summary

### By Function

**State Management:**
- `src/context/AppContext.tsx`
- `src/context/CartContext.tsx`

**API Communication:**
- `src/api/baseUrl.ts`
- `src/api/restaurants.ts`
- `src/api/meals.ts`
- `src/api/orders.ts`

**Type Definitions:**
- `src/types/restaurant.ts`
- `src/types/meal.ts`
- `src/types/user.ts`
- `src/types/cart.ts`
- `src/types/order.ts`

**Layout & Navigation:**
- `src/layout/MiniAppShell.tsx`
- `src/layout/Header.tsx`
- `src/layout/BottomBarCart.tsx`
- `src/router.tsx`

**Pages:**
- `src/pages/Splash/SplashPage.tsx`
- `src/pages/CafeList/CafeListPage.tsx`
- `src/pages/Menu/MenuPage.tsx`
- `src/pages/Cart/CartPage.tsx`
- `src/pages/Checkout/CheckoutPage.tsx`
- `src/pages/Profile/ProfilePage.tsx`

**Reusable Components:**
- `src/components/menu/MenuItemCard.tsx`
- `src/components/cart/CartItemRow.tsx`

**Integration:**
- `src/telegram/initTelegram.ts`

**Entry Points:**
- `src/main.tsx`
- `src/App.tsx`
- `index.html`

---

## 📊 Route Structure

```
/                    → SplashPage
/cafes               → CafeListPage
/cafes/:id/menu      → MenuPage
/cart                → CartPage
/checkout            → CheckoutPage
/profile             → ProfilePage
```

---

## 🔄 Data Flow

1. **User selects restaurant** → Updates `AppContext.selectedRestaurant`
2. **User adds items to cart** → Updates `CartContext.items`
3. **User navigates to checkout** → Reads from both contexts
4. **User submits order** → Calls `createOrder()` API
5. **Order created** → Shows success message, navigates back

---

## 🎨 Design System

- **Colors:** Slate palette (slate-50 to slate-900)
- **Spacing:** Tailwind spacing scale (p-2, p-3, p-4, etc.)
- **Border Radius:** rounded-2xl (cards), rounded-full (buttons)
- **Shadows:** shadow-sm, shadow-md, shadow-lg
- **Typography:** text-sm (base), text-xs (small), text-lg (headings)

---

## 📝 Notes

- All components use TypeScript strict mode
- No `any` types used
- Mobile-first responsive design
- Bento-style UI with soft shadows and rounded corners
- Consistent spacing and padding throughout
- Error handling and loading states implemented
- Search functionality on CafeList and Menu pages
- Sticky category tabs with auto-highlight on Menu page

