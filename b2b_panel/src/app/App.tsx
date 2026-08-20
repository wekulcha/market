import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { useAuth, AuthProvider } from '../auth/AuthContext';
import { RoleGuard } from '../components/RoleGuard';
import { LoadingPanel } from '../components/ui';
import { AdminShell } from '../features/admin/AdminShell';
import { DashboardPage } from '../features/admin/AdminDashboard';
import { ModerationPage } from '../features/admin/AdminModeration';
import {
  AdminCatalogPage,
  AdminOrdersPage,
  AuditPage,
  BuyersPage,
  DeliveryPage,
  InvitesPage,
  NotificationsPage,
  SellersPage,
  SettingsPage,
  SubscriptionsPage,
} from '../features/admin/AdminResources';
import {
  BuyerCartPage,
  BuyerCatalogPage,
  BuyerCheckoutPage,
  BuyerHomePage,
  BuyerOrdersPage,
  BuyerProfilePage,
} from '../features/buyer/BuyerPages';
import { BuyerShell } from '../features/buyer/BuyerShell';
import {
  SellerHomePage,
  SellerOfferFormPage,
  SellerOffersPage,
  SellerOrdersPage,
} from '../features/seller/SellerPages';
import { SellerShell } from '../features/seller/SellerShell';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
    mutations: { retry: 0 },
  },
});

function HomeRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <LoadingPanel label="Открываем кабинет…" />;
  if (user?.roles.some((role) => role === 'ADMIN' || role === 'SUPERADMIN')) return <Navigate to="/admin" replace />;
  if (user?.roles.includes('SELLER')) return <Navigate to="/seller" replace />;
  return <Navigate to="/buyer" replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/buyer" element={<RoleGuard required="BUYER"><BuyerShell /></RoleGuard>}>
        <Route index element={<BuyerHomePage />} />
        <Route path="catalog" element={<BuyerCatalogPage />} />
        <Route path="catalog/:offerId" element={<BuyerCatalogPage />} />
        <Route path="cart" element={<BuyerCartPage />} />
        <Route path="checkout" element={<BuyerCheckoutPage />} />
        <Route path="orders" element={<BuyerOrdersPage />} />
        <Route path="orders/:orderId" element={<BuyerOrdersPage />} />
        <Route path="subscription" element={<BuyerHomePage />} />
        <Route path="profile" element={<BuyerProfilePage />} />
      </Route>
      <Route path="/seller" element={<RoleGuard required="SELLER"><SellerShell /></RoleGuard>}>
        <Route index element={<SellerHomePage />} />
        <Route path="offers" element={<SellerOffersPage />} />
        <Route path="offers/:offerId" element={<SellerOffersPage />} />
        <Route path="offers/new" element={<SellerOfferFormPage />} />
        <Route path="offers/:offerId/edit" element={<SellerOfferFormPage />} />
        <Route path="orders" element={<SellerOrdersPage />} />
      </Route>
      <Route path="/admin" element={<RoleGuard required="ADMIN"><AdminShell /></RoleGuard>}>
        <Route index element={<DashboardPage />} />
        <Route path="moderation" element={<ModerationPage />} />
        <Route path="offers/:offerId" element={<ModerationPage />} />
        <Route path="catalog" element={<AdminCatalogPage />} />
        <Route path="sellers" element={<SellersPage />} />
        <Route path="buyers" element={<BuyersPage />} />
        <Route path="subscriptions" element={<SubscriptionsPage />} />
        <Route path="orders" element={<AdminOrdersPage />} />
        <Route path="delivery" element={<DeliveryPage />} />
        <Route path="invites" element={<InvitesPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<HomeRedirect />} />
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
