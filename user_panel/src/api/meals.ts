import type { Meal } from '../types/meal';
import { BASE_URL } from './baseUrl';

/** Backend MealDto (camelCase) */
interface MealDto {
  id: number;
  restaurantId: number;
  name: string;
  description: string | null;
  weight: number | null;
  calorie: number | null;
  imageLink: string | null;
  category: string | null;
  price: number;
  available: boolean;
}

function toMeal(d: MealDto): Meal {
  return {
    id: d.id,
    restaurant_id: d.restaurantId,
    name: d.name,
    description: d.description,
    weight: d.weight,
    calorie: d.calorie,
    image_link: d.imageLink ?? null,
    category: d.category ?? 'OTHER',
    price: Number(d.price),
    is_available: d.available ?? true,
  };
}

export async function fetchMealsByRestaurant(restaurantId: number): Promise<Meal[]> {
  const resp = await fetch(`${BASE_URL}/restaurants/${restaurantId}/meals?availableOnly=true`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch meals for restaurant ${restaurantId}: ${resp.status}`);
  }
  const data = (await resp.json()) as MealDto[];
  return data.map(toMeal);
}
