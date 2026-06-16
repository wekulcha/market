export interface AdminRestaurantOverview {
  id: number;
  name: string;
  address: string;
  imageLink?: string | null;
  isActive?: boolean;
  staff: { id: number; userId: number; restaurantId: number; permission: string }[];
  meals: { id: number; restaurantId: number; name: string; price: number; available: boolean }[];
  orderHistory: { id: number; status: string; total: number; createdAt: string }[];
}

export interface AdminUserOverview {
  id: number;
  username: string;
  phone: string;
  email: string | null;
  address: string | null;
  isActive?: boolean;
  courier: boolean;
  staffAssignments: { restaurantId: number; restaurantName: string; permission: string }[];
  orderHistory: { orderId: number; restaurantName: string; total: number; createdAt: string }[];
}

export interface CreateRestaurantRequest {
  name: string;
  address: string;
  /** Telegram user id (users.id) — владелец магазина */
  ownerUserId: number;
}

export interface AdminOrderSummary {
  id: number;
  status: string;
  createdAt: string;
  updatedAt?: string | null;
  orderType: string;
  restaurantId: number;
  restaurantName: string;
  userId: number;
  username: string | null;
  total: number | string;
}

export interface AdminOrderPositionLine {
  mealName: string;
  mealWeight?: number | null;
  finalWeightGrams?: number | null;
  finalWeightGramsList?: number[];
  quantity: number;
  unitPrice: number | string;
  totalPrice: number | string;
}

export interface AdminOrderDetail {
  id: number;
  status: string;
  createdAt: string;
  updatedAt?: string | null;
  orderType: string;
  deliveryAddress: string | null;
  tableNumber?: string | null;
  restaurantId: number;
  restaurantName: string;
  userId: number;
  username: string | null;
  phone: string | null;
  itemsTotal: number | string;
  deliveryFee: number | string;
  serviceFee: number | string;
  total: number | string;
  positions: AdminOrderPositionLine[];
}

export interface AdminStatsSummary {
  users: number;
  restaurants: number;
  orders: number;
}

export interface AdminUserActivityLog {
  id: number;
  userId: number;
  event: string;
  source: string;
  metadata: Record<string, unknown> | null;
  createdAt: string;
}
