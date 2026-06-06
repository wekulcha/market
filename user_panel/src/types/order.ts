import type { ServiceType } from '../context/AppContext';

export type PaymentMethod = 'CASH' | 'TRANSFER';
export type OrderStatus = 'CREATED' | 'ACCEPTED' | 'COOKING' | 'DELIVERY' | 'DONE' | 'CANCELLED';

export interface OrderItemPayload {
  meal_id: number;
  quantity: number;
  price: number;
}

export interface CreateOrderPayload {
  restaurant_id: number;
  service_type: ServiceType;
  delivery_address: string | null;
  /** Для заказа в зале */
  table_number: string | null;
  comment: string | null;
  username: string | null;
  phone: string;
  payment_method: PaymentMethod;
  items: OrderItemPayload[];
  items_total: number;
  delivery_fee: number;
  service_fee: number;
  total: number;
}

export interface OrderResponse {
  id: number;
  total: number;
  createdAt: string;
}

export interface UserOrder {
  id: number;
  status: OrderStatus;
  user_id: number | null;
  delivery_address: string | null;
  table_number: string | null;
  comment?: string | null;
  restaurant_id: number | null;
  created_at: string | null;
  updated_at: string | null;
  courier_id: number | null;
  order_type: ServiceType | null;
  items_total: number | null;
  delivery_fee: number | null;
  service_fee: number | null;
  total: number | null;
  is_paid?: boolean | null;
}
