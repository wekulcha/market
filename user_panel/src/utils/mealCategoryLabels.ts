import { PRODUCT_CATEGORIES, productCategoryLabel, productCategoryRank } from './productCategories';

/** Подписи категорий товаров (ключ — значение backend MealCategory). */
export const MEAL_CATEGORY_LABELS: Record<string, string> = Object.fromEntries(
  PRODUCT_CATEGORIES.map((category) => [category.key, category.label])
);

export const MEAL_CATEGORY_ORDER: string[] = PRODUCT_CATEGORIES.map((category) => category.key);

export function mealCategoryLabel(cat: string | null | undefined): string {
  return productCategoryLabel(cat);
}

export function mealCategoryRank(cat: string | null | undefined): number {
  return productCategoryRank(cat);
}
