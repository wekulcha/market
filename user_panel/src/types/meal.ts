export interface Meal {
  id: number;
  restaurant_id: number;
  name: string;
  description: string | null;
  weight: number | null;
  calorie: number | null;
  image_link: string;
  category: string | null;
  price: number;
  is_available: boolean;
}
