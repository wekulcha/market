/** Соответствует backend MealCategory; подписи для админки. */
export const MEAL_CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: 'VEGETABLES_HERBS', label: 'Овощи, грибы и зелень' },
  { value: 'FRUITS_BERRIES', label: 'Фрукты и ягоды' },
  { value: 'DAIRY_EGGS', label: 'Молочные продукты и яйца' },
  { value: 'DRIED_FRUITS_NUTS', label: 'Сухофрукты и орехи' },
  { value: 'MEAT_POULTRY', label: 'Мясо и птица' },
  { value: 'FISH_SEAFOOD', label: 'Рыба и морепродукты' },
  { value: 'SAUSAGE', label: 'Колбаса и сосиски' },
  { value: 'PASTA_GRAINS', label: 'Макароны и крупы' },
  { value: 'OILS_SAUCES_SPICES', label: 'Масло, соусы и специи' },
  { value: 'CANNED_PICKLES', label: 'Консервы и соленья' },
  { value: 'BREAD_BAKERY', label: 'Хлеб и выпечка' },
  { value: 'SWEETS', label: 'Сладости' },
];

export function mealCategoryLabel(value: string | null | undefined): string {
  if (!value) return '';
  const o = MEAL_CATEGORY_OPTIONS.find((x) => x.value === value);
  return o?.label ?? value;
}

export function mealCategoryRank(value: string | null | undefined): number {
  if (!value) return 999;
  const index = MEAL_CATEGORY_OPTIONS.findIndex((option) => option.value === value);
  return index === -1 ? 999 : index;
}
