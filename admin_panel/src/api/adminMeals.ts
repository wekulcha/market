import { BASE_URL } from "./baseUrl";
import { Meal, AdminMealCreate } from "../types/adminMeal";
import { buildAdminApiJsonHeaders, getTelegramInitData } from "../telegram/initTelegram";

async function readApiError(resp: Response, fallback: string): Promise<never> {
  let detail = "";
  try {
    const text = (await resp.text()).trim();
    if (text) {
      try {
        const parsed = JSON.parse(text) as { detail?: unknown };
        if (typeof parsed.detail === "string") {
          detail = parsed.detail;
        } else {
          detail = text;
        }
      } catch {
        detail = text;
      }
    }
  } catch {
    // ignore body parse issues
  }
  throw new Error(detail || fallback);
}

/** Backend MealDto (camelCase) */
interface MealDto {
  id: number;
  restaurantId: number;
  name: string;
  description: string | null;
  weight: number | null;
  calorie: number | null;
  imageLink: string;
  category: string;
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
    image_link: d.imageLink ?? "",
    category: d.category,
    price: Number(d.price),
    is_available: d.available ?? true,
  };
}

export async function uploadMealImage(restaurantId: number, file: File): Promise<string> {
  const init = getTelegramInitData();
  const fd = new FormData();
  fd.append("file", file);
  const headers: Record<string, string> = {};
  if (init) headers["X-Telegram-Init-Data"] = init;
  const resp = await fetch(
    `${BASE_URL}/meal-assets/upload?restaurantId=${restaurantId}`,
    {
      method: "POST",
      headers,
      body: fd,
    }
  );
  if (!resp.ok) {
    throw new Error(`Failed to upload image: ${resp.status}`);
  }
  const j = (await resp.json()) as { path: string };
  return j.path;
}

export async function fetchAdminMeals(restaurantId: number): Promise<Meal[]> {
  const resp = await fetch(
    `${BASE_URL}/restaurants/${restaurantId}/meals?availableOnly=false`,
    { headers: buildAdminApiJsonHeaders() }
  );
  if (!resp.ok) {
    throw new Error(`Failed to fetch meals: ${resp.status}`);
  }
  const data = (await resp.json()) as MealDto[];
  return data.map(toMeal);
}

export async function createAdminMeal(
  restaurantId: number,
  payload: AdminMealCreate
): Promise<Meal> {
  const body = {
    restaurantId,
    name: payload.name,
    description: payload.description ?? null,
    weight: payload.weight ?? null,
    calorie: payload.calorie ?? null,
    imageLink: payload.image_link,
    category: payload.category,
    price: payload.price,
    available: payload.is_available ?? true,
  };
  const resp = await fetch(`${BASE_URL}/meals`, {
    method: "POST",
    headers: buildAdminApiJsonHeaders(),
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    await readApiError(resp, `Failed to create meal: ${resp.status}`);
  }
  const d = (await resp.json()) as MealDto;
  return toMeal(d);
}

export async function updateAdminMeal(
  mealId: number,
  meal: Meal,
  updates: Partial<
    Pick<
      Meal,
      | "name"
      | "description"
      | "weight"
      | "calorie"
      | "image_link"
      | "category"
      | "price"
      | "is_available"
    >
  >
): Promise<Meal> {
  const body = {
    id: meal.id,
    restaurantId: meal.restaurant_id,
    name: updates.name ?? meal.name,
    description: updates.description ?? meal.description,
    weight: updates.weight ?? meal.weight,
    calorie: updates.calorie ?? meal.calorie,
    imageLink: updates.image_link ?? meal.image_link,
    category: updates.category ?? meal.category,
    price: updates.price ?? meal.price,
    available: updates.is_available ?? meal.is_available,
  };
  const resp = await fetch(`${BASE_URL}/meals/${mealId}`, {
    method: "PUT",
    headers: buildAdminApiJsonHeaders(),
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    await readApiError(resp, `Failed to update meal: ${resp.status}`);
  }
  const d = (await resp.json()) as MealDto;
  return toMeal(d);
}

export async function updateMealAvailability(
  mealId: number,
  meal: Meal,
  isAvailable: boolean
): Promise<Meal> {
  return updateAdminMeal(mealId, meal, { is_available: isAvailable });
}

export async function updateCategoryAvailability(
  restaurantId: number,
  category: string,
  isAvailable: boolean
): Promise<Meal[]> {
  const resp = await fetch(`${BASE_URL}/meals/category-availability`, {
    method: "PATCH",
    headers: buildAdminApiJsonHeaders(),
    body: JSON.stringify({
      restaurantId,
      category,
      available: isAvailable,
    }),
  });
  if (!resp.ok) {
    await readApiError(resp, `Failed to update category availability: ${resp.status}`);
  }
  const data = (await resp.json()) as MealDto[];
  return data.map(toMeal);
}

export async function deleteMeal(mealId: number): Promise<void> {
  const resp = await fetch(`${BASE_URL}/meals/${mealId}`, {
    method: "DELETE",
    headers: buildAdminApiJsonHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Failed to delete meal: ${resp.status}`);
  }
}
