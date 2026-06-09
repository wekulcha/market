import type {
  AdminOrderDetail,
  AdminOrderSummary,
  AdminRestaurantOverview,
  AdminStatsSummary,
  AdminUserActivityLog,
  AdminUserOverview,
  CreateRestaurantRequest,
} from "../types/admin";
import { apiFetchJson } from "./client";

export async function fetchAdminRestaurants(): Promise<AdminRestaurantOverview[]> {
  return apiFetchJson<AdminRestaurantOverview[]>("/admin/restaurants", {}, { auth: true });
}

export async function createRestaurant(
  body: CreateRestaurantRequest
): Promise<{ id: number; name: string; address: string }> {
  return apiFetchJson<{ id: number; name: string; address: string }>(
    "/admin/restaurants",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    { auth: true }
  );
}

export async function fetchAdminUsers(): Promise<AdminUserOverview[]> {
  return apiFetchJson<AdminUserOverview[]>("/admin/users", {}, { auth: true });
}

export async function fetchAdminOrders(q?: string): Promise<AdminOrderSummary[]> {
  const qs = q?.trim() ? `?q=${encodeURIComponent(q.trim())}` : "";
  return apiFetchJson<AdminOrderSummary[]>(`/admin/orders${qs}`, {}, { auth: true });
}

export async function fetchAdminOrderDetail(orderId: number): Promise<AdminOrderDetail> {
  return apiFetchJson<AdminOrderDetail>(`/admin/orders/${orderId}`, {}, { auth: true });
}

export async function fetchAdminStats(): Promise<AdminStatsSummary> {
  return apiFetchJson<AdminStatsSummary>("/admin/stats/summary", {}, { auth: true });
}

export async function fetchAdminUserActivity(
  userId: number,
  limit = 100
): Promise<AdminUserActivityLog[]> {
  return apiFetchJson<AdminUserActivityLog[]>(
    `/admin/users/${userId}/activity?limit=${limit}`,
    {},
    { auth: true }
  );
}

export async function setUserActive(userId: number, isActive: boolean): Promise<void> {
  await apiFetchJson(
    `/admin/users/${userId}/status`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ isActive }),
    },
    { auth: true }
  );
}

export async function deleteAdminUser(userId: number): Promise<void> {
  await apiFetchJson(`/admin/users/${userId}`, { method: "DELETE" }, { auth: true });
}

export async function setRestaurantActive(restaurantId: number, isActive: boolean): Promise<void> {
  await apiFetchJson(
    `/admin/restaurants/${restaurantId}/status`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ isActive }),
    },
    { auth: true }
  );
}

export async function deleteAdminRestaurant(restaurantId: number): Promise<void> {
  await apiFetchJson(`/admin/restaurants/${restaurantId}`, { method: "DELETE" }, { auth: true });
}

export async function resetAdminRestaurantAnalytics(restaurantId: number): Promise<void> {
  await apiFetchJson(
    `/admin/restaurants/${restaurantId}/analytics`,
    { method: "DELETE" },
    { auth: true }
  );
}
