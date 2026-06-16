/** Backend OrderStatus enum. COOKING/DELIVERY are legacy-compatible. */
export type AdminOrderStatusCode =
  | "CREATED"
  | "ACCEPTED"
  | "COOKING"
  | "DELIVERY"
  | "DONE"
  | "CANCELLED";

export interface AdminOrderItem {
  id: number;
  meal_id: number;
  name: string;
  weight: number | null;
  requires_final_weight: boolean;
  final_weight_grams: number | null;
  final_weight_grams_list: number[];
  total_price: number;
  quantity: number;
}

/** Order from API (camelCase); items filled in UI from order-positions + meals */
export interface AdminOrder {
  id: number;
  status: AdminOrderStatusCode;
  createdAt: string;
  total: number;
  orderType: "DELIVERY" | "DINE_IN";
  deliveryAddress: string | null;
  tableNumber?: string | null;
  comment?: string | null;
  userId: number;
  restaurantId: number;
  itemsTotal?: number;
  deliveryFee?: number;
  serviceFee?: number;
  updatedAt?: string | null;
  courierId?: number | null;
  items?: AdminOrderItem[];
  username?: string | null;
  phone?: string;
  isPaid?: boolean;
}
