import type { AdminListItem, ApiList, DashboardKpi, InviteResult, ModerationOffer } from '../types/domain';
import { apiJson, jsonRequest } from './client';

function list(path: string, page = 1, search = ''): Promise<ApiList<AdminListItem>> {
  const params = new URLSearchParams({ page: String(page) });
  if (search.trim()) params.set('search', search.trim());
  return apiJson<ApiList<AdminListItem>>(`/admin/${path}?${params}`);
}

export const adminApi = {
  dashboard: () => apiJson<DashboardKpi>('/admin/dashboard'),
  moderationOffers: () => apiJson<ApiList<ModerationOffer>>('/admin/offers?status=SUBMITTED,UNDER_REVIEW,APPROVED'),
  offers: (page = 1, search = '') => list('offers', page, search),
  sellers: (page = 1, search = '') => list('sellers', page, search),
  buyers: (page = 1, search = '') => list('buyers', page, search),
  subscriptions: (page = 1, search = '') => list('subscriptions', page, search),
  orders: (page = 1, search = '') => list('orders', page, search),
  deliveries: (page = 1, search = '') => list('deliveries', page, search),
  invites: (page = 1, search = '') => list('invites', page, search),
  notifications: (page = 1, search = '') => list('notifications', page, search),
  audit: (page = 1, search = '') => list('audit', page, search),
  settings: () => apiJson<Record<string, string | number | boolean>>('/admin/settings'),
  moderateOffer: (offerId: string, body: { decision: 'APPROVE' | 'REJECT' | 'REQUEST_CHANGES'; reason?: string | null }) =>
    apiJson<ModerationOffer>(`/admin/offers/${offerId}/moderate`, jsonRequest('POST', body)),
  priceOffer: (offerId: string, body: {
    markupType: 'PERCENT' | 'FIXED' | 'MANUAL';
    markupPercent?: number | null;
    fixedMarkupKopecks?: number | null;
    manualBuyerUnitPriceKopecks?: number | null;
  }) => apiJson<ModerationOffer>(`/admin/offers/${offerId}/pricing`, jsonRequest('POST', body)),
  publishOffer: (offerId: string) => apiJson<ModerationOffer>(`/admin/offers/${offerId}/publish`, jsonRequest('POST', {})),
  setSellerStatus: (sellerId: string, status: 'VERIFIED' | 'SUSPENDED' | 'BLOCKED', reason: string) =>
    apiJson<AdminListItem>(`/admin/sellers/${sellerId}/status`, jsonRequest('POST', { status, reason })),
  createInvite: (body: { label: string; expiresInDays: number }) => apiJson<InviteResult>('/admin/invites', jsonRequest('POST', body)),
  transitionOrder: (orderId: string, status: string, comment: string | null) => apiJson(`/admin/orders/${orderId}/transition`, jsonRequest('POST', { status, comment })),
  createDelivery: (body: { orderId: string; courierName: string; pickupWindow: string; deliveryWindow: string }) => apiJson('/admin/deliveries', jsonRequest('POST', body)),
  updateDeliveryStatus: (
    deliveryId: string,
    status: 'PICKED_UP' | 'IN_DELIVERY' | 'DELIVERED' | 'CANCELED' | 'FAILED',
    comment: string | null = null,
  ) => apiJson(`/admin/deliveries/${deliveryId}/status`, jsonRequest('POST', { status, comment })),
  overrideSubscription: (body: { buyerId: string; status: string; expiresAt: string; reason: string }) => apiJson('/admin/subscriptions/override', jsonRequest('POST', body)),
  updateSettings: (body: Record<string, string | number | boolean>) => apiJson<Record<string, string | number | boolean>>('/admin/settings', jsonRequest('PATCH', body)),
};
