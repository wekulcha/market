import type { CreateOrderPayload, OrderResponse, UserOrder } from '../types/order';
import { apiFetchJson } from './client';

interface OrderCheckoutBody {
  restaurantId: number;
  deliveryAddress: string | null;
  tableNumber: string | null;
  comment: string | null;
  orderType: 'DELIVERY' | 'DINE_IN';
  itemsTotal: number;
  deliveryFee: number;
  serviceFee: number;
  total: number;
  items: { mealId: number; quantity: number; unitPrice: number }[];
}

interface OrderDto {
  id: number;
  status: UserOrder['status'];
  userId: number | null;
  deliveryAddress: string | null;
  tableNumber: string | null;
  comment?: string | null;
  restaurantId: number | null;
  createdAt: string | null;
  updatedAt: string | null;
  courierId: number | null;
  orderType: UserOrder['order_type'];
  itemsTotal: number | string | null;
  deliveryFee: number | string | null;
  serviceFee: number | string | null;
  total: number | string | null;
  isPaid?: boolean | null;
  reviewRating?: number | null;
  reviewText?: string | null;
  reviewCreatedAt?: string | null;
}

function toNumber(value: number | string | null | undefined): number | null {
  if (value == null) return null;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function toUserOrder(dto: OrderDto): UserOrder {
  return {
    id: dto.id,
    status: dto.status,
    user_id: dto.userId,
    delivery_address: dto.deliveryAddress,
    table_number: dto.tableNumber ?? null,
    comment: dto.comment ?? null,
    restaurant_id: dto.restaurantId,
    created_at: dto.createdAt,
    updated_at: dto.updatedAt,
    courier_id: dto.courierId,
    order_type: dto.orderType,
    items_total: toNumber(dto.itemsTotal),
    delivery_fee: toNumber(dto.deliveryFee),
    service_fee: toNumber(dto.serviceFee),
    total: toNumber(dto.total),
    is_paid: dto.isPaid ?? null,
    review_rating: dto.reviewRating ?? null,
    review_text: dto.reviewText ?? null,
    review_created_at: dto.reviewCreatedAt ?? null,
  };
}

export async function createOrder(payload: CreateOrderPayload): Promise<OrderResponse> {
  const body: OrderCheckoutBody = {
    restaurantId: payload.restaurant_id,
    deliveryAddress: payload.delivery_address ?? null,
    tableNumber: payload.table_number ?? null,
    comment: payload.comment ?? null,
    orderType: payload.service_type,
    itemsTotal: payload.items_total,
    deliveryFee: payload.delivery_fee,
    serviceFee: payload.service_fee,
    total: payload.total,
    items: payload.items.map((item) => ({
      mealId: item.meal_id,
      quantity: item.quantity,
      unitPrice: item.price,
    })),
  };

  const dto = await apiFetchJson<OrderDto>(
    '/orders/checkout',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    { auth: true }
  );

  return {
    id: dto.id,
    total: toNumber(dto.total) ?? 0,
    createdAt: dto.createdAt ?? new Date().toISOString(),
  };
}

export async function fetchMyOrders(): Promise<UserOrder[]> {
  const dto = await apiFetchJson<OrderDto[]>('/orders/my', {}, { auth: true });
  return dto.map(toUserOrder);
}

export async function cancelOrder(orderId: number): Promise<void> {
  await apiFetchJson<unknown>(
    `/orders/${orderId}/cancel`,
    { method: 'POST' },
    { auth: true }
  );
}

export async function fetchOrderPositionsForUser(
  orderId: number
): Promise<{ meal_id: number; name: string; quantity: number; total_price: number }[]> {
  const resp = await apiFetchJson<
    { id: number; mealId: number; mealName?: string | null; orderId: number; quantity: number; totalPrice: number }[]
  >(`/order-positions?orderId=${orderId}`, {}, { auth: true });

  const mealIds = [...new Set(resp.map((p) => p.mealId))];
  const nameMap = new Map<number, string>();
  for (const mid of mealIds) {
    const known = resp.find((p) => p.mealId === mid && p.mealName);
    if (known?.mealName) {
      nameMap.set(mid, known.mealName);
      continue;
    }
    const meal = await apiFetchJson<{ name: string }>(`/meals/${mid}`);
    nameMap.set(mid, meal.name);
  }
  return resp.map((p) => ({
    meal_id: p.mealId,
    name: nameMap.get(p.mealId) ?? `#${p.mealId}`,
    quantity: p.quantity,
    total_price: Number(p.totalPrice ?? 0),
  }));
}
