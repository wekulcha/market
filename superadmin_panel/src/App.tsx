import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AuthContextProvider } from "./context/AuthContext";
import { SuperadminShell } from "./layout/SuperadminShell";
import { RestaurantsPage } from "./pages/RestaurantsPage";
import { UsersPage } from "./pages/UsersPage";
import { OrdersPage } from "./pages/OrdersPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ToolsPage } from "./pages/ToolsPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60 * 1000 } },
});

const router = createBrowserRouter([
  {
    path: "/",
    element: <SuperadminShell />,
    children: [
      { index: true, element: <RestaurantsPage /> },
      { path: "users", element: <UsersPage /> },
      { path: "orders", element: <OrdersPage /> },
      { path: "analytics", element: <AnalyticsPage /> },
      { path: "tools", element: <ToolsPage /> },
    ],
  },
]);

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthContextProvider>
        <RouterProvider router={router} />
      </AuthContextProvider>
    </QueryClientProvider>
  );
}
