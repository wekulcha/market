import type { ApiList, SellerOffer, SellerOrder, SellerProfile } from '../types/domain';
import { apiFetch, apiJson, jsonRequest } from './client';

export interface SellerOfferInput {
  name: string;
  description: string | null;
  category: string;
  procurementUnitPriceKopecks: number;
  currency: 'RUB';
  unit: SellerOffer['unit'];
  packageSize: string | null;
  totalQuantity: number;
  minimumQuantity: number;
  quantityStep: number;
  shelfLife: string | null;
  storageConditions: string | null;
  expiresAt: string | null;
}

export const sellerApi = {
  me: () => apiJson<SellerProfile>('/seller/me'),
  updateMe: (patch: Partial<SellerProfile>) => apiJson<SellerProfile>('/seller/me', jsonRequest('PATCH', patch)),
  offers: () => apiJson<ApiList<SellerOffer>>('/seller/offers'),
  offer: (offerId: string) => apiJson<SellerOffer>(`/seller/offers/${offerId}`),
  createOffer: (body: SellerOfferInput) => apiJson<SellerOffer>('/seller/offers', jsonRequest('POST', body)),
  updateOffer: (offerId: string, body: Partial<SellerOfferInput>) => apiJson<SellerOffer>(`/seller/offers/${offerId}`, jsonRequest('PATCH', body)),
  submitOffer: (offerId: string) => apiJson<SellerOffer>(`/seller/offers/${offerId}/submit`, jsonRequest('POST', {})),
  async uploadImage(offerId: string, file: File): Promise<string> {
    const form = new FormData();
    form.append('file', file);
    const response = await apiFetch(`/seller/offers/${offerId}/images`, { method: 'POST', body: form });
    if (!response.ok) throw new Error(`Не удалось загрузить изображение (${response.status})`);
    const value = (await response.json()) as { url: string };
    return value.url;
  },
  orders: () => apiJson<ApiList<SellerOrder>>('/seller/orders'),
  confirmOrder: (fulfillmentId: string) => apiJson<SellerOrder>(`/seller/orders/${fulfillmentId}/confirm`, jsonRequest('POST', {})),
  readyOrder: (fulfillmentId: string) => apiJson<SellerOrder>(`/seller/orders/${fulfillmentId}/ready`, jsonRequest('POST', {})),
};
