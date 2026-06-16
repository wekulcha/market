import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';

const SplashPage = lazy(() => import('./pages/Splash/SplashPage').then((m) => ({ default: m.SplashPage })));
const CafeListPage = lazy(() => import('./pages/CafeList/CafeListPage').then((m) => ({ default: m.CafeListPage })));
const MenuPage = lazy(() => import('./pages/Menu/MenuPage').then((m) => ({ default: m.MenuPage })));
const CartPage = lazy(() => import('./pages/Cart/CartPage').then((m) => ({ default: m.CartPage })));
const CheckoutPage = lazy(() => import('./pages/Checkout/CheckoutPage').then((m) => ({ default: m.CheckoutPage })));
const ProfilePage = lazy(() => import('./pages/Profile/ProfilePage').then((m) => ({ default: m.ProfilePage })));
const OrderHistoryPage = lazy(() =>
  import('./pages/OrderHistory/OrderHistoryPage').then((m) => ({ default: m.OrderHistoryPage }))
);
const ReviewsPage = lazy(() => import('./pages/Reviews/ReviewsPage').then((m) => ({ default: m.ReviewsPage })));

const PageFallback = () => (
  <div className="min-h-screen flex items-center justify-center bg-slate-100">
    <div className="w-8 h-8 border-2 border-slate-300 border-t-slate-700 rounded-full animate-spin" />
  </div>
);

export const router = createBrowserRouter([
  { path: '/', element: <Suspense fallback={<PageFallback />}><SplashPage /></Suspense> },
  { path: '/catalog', element: <Suspense fallback={<PageFallback />}><CafeListPage /></Suspense> },
  { path: '/catalog/:categoryKey', element: <Suspense fallback={<PageFallback />}><MenuPage /></Suspense> },
  { path: '/cafes', element: <Navigate to="/catalog" replace /> },
  { path: '/cafes/:restaurantId/menu', element: <Navigate to="/catalog" replace /> },
  { path: '/cart', element: <Suspense fallback={<PageFallback />}><CartPage /></Suspense> },
  { path: '/checkout', element: <Suspense fallback={<PageFallback />}><CheckoutPage /></Suspense> },
  { path: '/profile', element: <Suspense fallback={<PageFallback />}><ProfilePage /></Suspense> },
  { path: '/orders/history', element: <Suspense fallback={<PageFallback />}><OrderHistoryPage /></Suspense> },
  { path: '/reviews', element: <Suspense fallback={<PageFallback />}><ReviewsPage /></Suspense> },
]);
