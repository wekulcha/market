import type { Meal } from './meal';

export interface CartItem {
  meal: Meal;
  quantity: number;
}

export interface CartState {
  items: CartItem[];
}

