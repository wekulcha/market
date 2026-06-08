import type { Restaurant } from '../types/restaurant';
import { getConfiguredMarketRestaurantId, MARKET_BRAND_NAME } from '../config/market';
import { BASE_URL } from './baseUrl';

interface RestaurantDto {
  id: number;
  name: string;
  address: string;
  imageLink?: string | null;
  ordersAcceptTo?: string | null;
}

function mapRestaurant(d: RestaurantDto): Restaurant {
  return {
    id: d.id,
    name: d.name,
    address: d.address,
    imageLink: d.imageLink ?? null,
    ordersAcceptTo: d.ordersAcceptTo ?? null,
  };
}

export async function fetchRestaurants(): Promise<Restaurant[]> {
  const resp = await fetch(`${BASE_URL}/restaurants`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch restaurants: ${resp.status}`);
  }
  const raw = (await resp.json()) as RestaurantDto[];
  return raw.map(mapRestaurant);
}

export async function fetchRestaurantById(id: number): Promise<Restaurant> {
  const resp = await fetch(`${BASE_URL}/restaurants/${id}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch market store: ${resp.status}`);
  }
  const raw = (await resp.json()) as RestaurantDto;
  return mapRestaurant(raw);
}

export async function fetchMarketRestaurant(): Promise<Restaurant> {
  const configuredId = getConfiguredMarketRestaurantId();
  if (configuredId) {
    return fetchRestaurantById(configuredId);
  }

  const restaurants = await fetchRestaurants();
  const marketStore =
    restaurants.find((restaurant) => restaurant.name.toLowerCase().includes('market')) ??
    restaurants.find((restaurant) => restaurant.name.toLowerCase().includes('маркет')) ??
    restaurants[0];

  if (!marketStore) {
    throw new Error(`${MARKET_BRAND_NAME} не настроен: нет активного магазина в backend.`);
  }

  return marketStore;
}
