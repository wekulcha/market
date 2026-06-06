export const MARKET_BRAND_NAME = 'Kulcha Market';

export function getConfiguredMarketRestaurantId(): number | null {
  const raw = import.meta.env.VITE_MARKET_RESTAURANT_ID;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

