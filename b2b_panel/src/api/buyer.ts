import type {
  ApiList,
  BuyerCart,
  BuyerOffer,
  BuyerOrder,
  BuyerProfile,
  BuyerSubscription,
} from '../types/domain';
import { apiJson, jsonRequest } from './client';

export interface CatalogQuery {
  search?: string;
  category?: string;
  sort?: 'NEWEST' | 'PRICE_ASC' | 'PRICE_DESC' | 'EXPIRY_ASC';
  page?: number;
}

function queryString(query: CatalogQuery): string {
  const params = new URLSearchParams();
  if (query.search?.trim()) params.set('search', query.search.trim());
  if (query.category) params.set('category', query.category);
  if (query.sort) params.set('sort', query.sort);
  if (query.page) params.set('page', String(query.page));
  const value = params.toString();
  return value ? `?${value}` : '';
}

export const buyerApi = {
  me: () => apiJson<BuyerProfile>('/buyer/me'),
  updateMe: (patch: Partial<BuyerProfile>) => apiJson<BuyerProfile>('/buyer/me', jsonRequest('PATCH', patch)),
  subscription: () => apiJson<BuyerSubscription>('/buyer/subscription'),
  createSubscriptionPayment: (idempotencyKey = crypto.randomUUID()) => {
    return apiJson<{ id: string; status: string; paymentUrl: string | null }>('/buyer/subscription/payments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({ idempotencyKey }),
    });
  },
  confirmMockSubscriptionPayment: (paymentId: string) =>
    apiJson<{ status: string; subscriptionEndsAt: string }>(
      `/buyer/subscription/payments/${paymentId}/mock-confirm`,
      jsonRequest('POST', {}),
    ),
  catalog: (query: CatalogQuery) => apiJson<ApiList<BuyerOffer>>(`/buyer/catalog${queryString(query)}`),
  offer: (offerId: string) => apiJson<BuyerOffer>(`/buyer/catalog/${offerId}`),
  cart: () => apiJson<BuyerCart>('/buyer/cart'),
  addCartItem: (offerId: string, quantity: number) => apiJson<BuyerCart>('/buyer/cart/items', jsonRequest('POST', { offerId, quantity })),
  updateCartItem: (itemId: string, quantity: number) => apiJson<BuyerCart>(`/buyer/cart/items/${itemId}`, jsonRequest('PATCH', { quantity })),
  removeCartItem: (itemId: string) => apiJson<BuyerCart>(`/buyer/cart/items/${itemId}`, { method: 'DELETE' }),
  createOrder: (body: {
    addressId: string;
    recipientName: string;
    recipientPhone: string;
    deliveryWindow: string | null;
    comment: string | null;
    paymentMethod: 'PAY_ON_DELIVERY' | 'BANK_TRANSFER' | 'MANUAL';
    idempotencyKey: string;
    termsAccepted: true;
  }) => apiJson<BuyerOrder>('/buyer/orders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': body.idempotencyKey },
    body: JSON.stringify(body),
  }),
  orders: () => apiJson<ApiList<BuyerOrder>>('/buyer/orders'),
  order: (orderId: string) => apiJson<BuyerOrder>(`/buyer/orders/${orderId}`),
};
