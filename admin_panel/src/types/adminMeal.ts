export interface AdminMealCreate {
  name: string;
  description?: string | null;
  weight?: number | null;
  calorie?: number | null;
  image_link?: string | null;
  category: string;
  price: number;
  is_available?: boolean;
}

export interface Meal {
  id: number;
  name: string;
  description: string | null;
  weight: number | null;
  calorie: number | null;
  image_link: string | null;
  category: string;
  price: number;
  is_available: boolean;
  restaurant_id: number;
}
