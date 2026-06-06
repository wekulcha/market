import type { AdminRestaurant } from '../types/adminRestaurant';

export const MARKET_BRAND_NAME = 'Kulcha Market';

export function getConfiguredMarketRestaurantId(): number | null {
  const raw = import.meta.env.VITE_MARKET_RESTAURANT_ID;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function selectMarketRestaurant(restaurants: AdminRestaurant[]): AdminRestaurant | null {
  const configuredId = getConfiguredMarketRestaurantId();
  if (configuredId) {
    return restaurants.find((restaurant) => restaurant.id === configuredId) ?? restaurants[0] ?? null;
  }

  return (
    restaurants.find((restaurant) => restaurant.name.toLowerCase().includes('market')) ??
    restaurants.find((restaurant) => restaurant.name.toLowerCase().includes('маркет')) ??
    restaurants[0] ??
    null
  );
}

