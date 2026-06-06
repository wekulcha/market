import React, { lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthContextProvider } from "./context/AuthContext";
import { AdminAppShell } from "./layout/AdminAppShell";
import { PrintTicketPage } from "./pages/PrintTicket/PrintTicketPage";

const AdminCafeListPage = lazy(() =>
  import("./pages/AdminCafeList/AdminCafeListPage").then((m) => ({ default: m.AdminCafeListPage }))
);
const AdminRestaurantPage = lazy(() =>
  import("./pages/AdminRestaurant/AdminRestaurantPage").then((m) => ({ default: m.AdminRestaurantPage }))
);
const AdminProfilePage = lazy(() =>
  import("./pages/AdminProfile/AdminProfilePage").then((m) => ({ default: m.AdminProfilePage }))
);

const PageFallback = () => (
  <div className="flex-1 flex items-center justify-center bg-slate-50">
    <div className="w-8 h-8 border-2 border-slate-300 border-t-slate-700 rounded-full animate-spin" />
  </div>
);

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60 * 1000 } },
});

export const App: React.FC = () => {
  if (typeof window !== "undefined" && window.location.pathname === "/print-ticket") {
    return <PrintTicketPage />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <AuthContextProvider>
        <BrowserRouter>
          <AdminAppShell>
            <Suspense fallback={<PageFallback />}>
              <Routes>
                <Route path="/" element={<AdminCafeListPage />} />
                <Route path="/restaurants/:id" element={<AdminRestaurantPage />} />
                <Route path="/profile" element={<AdminProfilePage />} />
              </Routes>
            </Suspense>
          </AdminAppShell>
        </BrowserRouter>
      </AuthContextProvider>
    </QueryClientProvider>
  );
};
