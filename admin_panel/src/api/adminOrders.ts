import { BASE_URL } from "./baseUrl";
import { buildAdminApiJsonHeaders } from "../telegram/initTelegram";
import { AdminOrder, AdminOrderStatusCode } from "../types/adminOrder";

export type AdminOrderFilterStatus =
  | "ALL"
  | AdminOrderStatusCode;

/** Backend OrderDto (camelCase) */
interface OrderDto {
  id: number;
  status: AdminOrderStatusCode;
  userId: number;
  deliveryAddress: string | null;
  tableNumber: string | null;
  comment: string | null;
  restaurantId: number;
  createdAt: string;
  updatedAt: string | null;
  courierId: number | null;
  orderType: "DELIVERY" | "DINE_IN";
  itemsTotal: number;
  deliveryFee: number;
  serviceFee: number;
  total: number;
  isPaid?: boolean;
}

function toAdminOrder(d: OrderDto): AdminOrder {
  return {
    id: d.id,
    status: d.status,
    createdAt: d.createdAt,
    total: Number(d.total),
    orderType: d.orderType,
    deliveryAddress: d.deliveryAddress,
    tableNumber: d.tableNumber,
    comment: d.comment,
    userId: d.userId,
    restaurantId: d.restaurantId,
    itemsTotal: Number(d.itemsTotal),
    deliveryFee: Number(d.deliveryFee),
    serviceFee: Number(d.serviceFee),
    updatedAt: d.updatedAt ?? null,
    courierId: d.courierId ?? null,
    isPaid: d.isPaid ?? false,
  };
}

export async function fetchAdminOrders(
  restaurantId: number,
  status: AdminOrderFilterStatus = "ALL",
  options?: { todayOnly?: boolean }
): Promise<AdminOrder[]> {
  const params = new URLSearchParams();
  params.set("restaurantId", String(restaurantId));
  if (status && status !== "ALL") {
    params.set("status", status);
  }
  if (options?.todayOnly) {
    params.set("todayOnly", "true");
  }
  const url = `${BASE_URL}/orders?${params.toString()}`;
  const resp = await fetch(url, { headers: buildAdminApiJsonHeaders() });
  if (!resp.ok) {
    throw new Error(`Failed to fetch admin orders: ${resp.status}`);
  }
  const data = (await resp.json()) as OrderDto[];
  return data.map(toAdminOrder);
}

export async function patchOrderPaid(orderId: number, isPaid: boolean): Promise<AdminOrder> {
  const resp = await fetch(`${BASE_URL}/orders/${orderId}/paid`, {
    method: "PATCH",
    headers: { ...buildAdminApiJsonHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ isPaid }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to patch paid: ${resp.status}`);
  }
  const d = (await resp.json()) as OrderDto;
  return toAdminOrder(d);
}

export async function updateAdminOrderStatus(
  orderId: number,
  status: AdminOrderStatusCode,
  currentOrder: AdminOrder
): Promise<AdminOrder> {
  const body = {
    id: currentOrder.id,
    status,
    userId: currentOrder.userId,
    deliveryAddress: currentOrder.deliveryAddress,
    tableNumber: currentOrder.tableNumber ?? null,
    comment: currentOrder.comment ?? null,
    restaurantId: currentOrder.restaurantId,
    createdAt: currentOrder.createdAt,
    updatedAt: currentOrder.updatedAt ?? null,
    courierId: currentOrder.courierId ?? null,
    orderType: currentOrder.orderType,
    itemsTotal: currentOrder.itemsTotal ?? 0,
    deliveryFee: currentOrder.deliveryFee ?? 0,
    serviceFee: currentOrder.serviceFee ?? 0,
    total: currentOrder.total,
    isPaid: currentOrder.isPaid ?? false,
  };
  const resp = await fetch(`${BASE_URL}/orders/${orderId}`, {
    method: "PUT",
    headers: buildAdminApiJsonHeaders(),
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw new Error(`Failed to update order status: ${resp.status}`);
  }
  const d = (await resp.json()) as OrderDto;
  return toAdminOrder(d);
}

export async function fetchOrderPositions(orderId: number): Promise<{ meal_id: number; name: string; quantity: number }[]> {
  const resp = await fetch(`${BASE_URL}/order-positions?orderId=${orderId}`, {
    headers: buildAdminApiJsonHeaders(),
  });
  if (!resp.ok) throw new Error(`Failed to fetch order positions: ${resp.status}`);
  const positions = (await resp.json()) as { id: number; mealId: number; orderId: number; quantity: number; unitPrice: number; totalPrice: number }[];
  const mealIds = [...new Set(positions.map((p) => p.mealId))];
  const nameMap = new Map<number, string>();
  await Promise.all(
    mealIds.map(async (mid) => {
      const mResp = await fetch(`${BASE_URL}/meals/${mid}`);
      if (mResp.ok) {
        const meal = (await mResp.json()) as { name: string };
        nameMap.set(mid, meal.name);
      } else {
        nameMap.set(mid, `#${mid}`);
      }
    })
  );
  const result: { meal_id: number; name: string; quantity: number }[] = positions.map((p) => ({
    meal_id: p.mealId,
    name: nameMap.get(p.mealId) ?? `#${p.mealId}`,
    quantity: p.quantity,
  }));
  return result;
}

export async function fetchUser(userId: number): Promise<{ username: string; phone: string } | null> {
  const resp = await fetch(`${BASE_URL}/users/${userId}`, {
    headers: buildAdminApiJsonHeaders(),
  });
  if (!resp.ok) return null;
  const u = (await resp.json()) as { username: string; phone: string };
  return u;
}
