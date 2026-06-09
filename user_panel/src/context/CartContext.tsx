import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from 'react';
import type { Meal } from '../types/meal';
import type { CartItem } from '../types/cart';
import { useAppContext } from './AppContext';
import { logUserActivity } from '../api/activity';

const STORAGE_KEY = 'kulcha_market_cart_v1';

interface CartContextValue {
  items: CartItem[];
  totalItems: number;
  addItem: (meal: Meal) => void;
  increment: (mealId: number) => void;
  decrement: (mealId: number) => void;
  getItemQuantity: (mealId: number) => number;
  clearCart: () => void;
}

const CartContext = createContext<CartContextValue | undefined>(undefined);

export const CartContextProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { selectedRestaurant, setSelectedRestaurant } = useAppContext();
  const [items, setItems] = useState<CartItem[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        setHydrated(true);
        return;
      }
      const data = JSON.parse(raw) as { restaurant: { id: number; name: string; address: string }; items: CartItem[] };
      if (data?.restaurant && Array.isArray(data.items)) {
        setSelectedRestaurant(data.restaurant);
        setItems(data.items);
      }
    } catch {
      // ignore corrupt storage
    }
    setHydrated(true);
  }, [setSelectedRestaurant]);

  useEffect(() => {
    if (!hydrated) return;
    if (!selectedRestaurant || items.length === 0) {
      localStorage.removeItem(STORAGE_KEY);
      return;
    }
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ restaurant: selectedRestaurant, items })
      );
    } catch {
      // quota / private mode
    }
  }, [items, selectedRestaurant, hydrated]);

  const getItemQuantity = useCallback(
    (mealId: number): number => {
      const item = items.find((it) => it.meal.id === mealId);
      return item ? item.quantity : 0;
    },
    [items]
  );

  const addItem = useCallback((meal: Meal) => {
    logUserActivity('cart_add_item', { mealId: meal.id, category: meal.category });
    setItems((prev) => {
      const existing = prev.find((it) => it.meal.id === meal.id);
      if (!existing) {
        return [...prev, { meal, quantity: 1 }];
      }
      return prev.map((it) =>
        it.meal.id === meal.id ? { ...it, quantity: it.quantity + 1 } : it
      );
    });
  }, []);

  const increment = useCallback((mealId: number) => {
    logUserActivity('cart_increment_item', { mealId });
    setItems((prev) =>
      prev.map((it) =>
        it.meal.id === mealId ? { ...it, quantity: it.quantity + 1 } : it
      )
    );
  }, []);

  const decrement = useCallback((mealId: number) => {
    logUserActivity('cart_decrement_item', { mealId });
    setItems((prev) =>
      prev
        .map((it) =>
          it.meal.id === mealId ? { ...it, quantity: it.quantity - 1 } : it
        )
        .filter((it) => it.quantity > 0)
    );
  }, []);

  const clearCart = useCallback(() => {
    logUserActivity('cart_clear');
    setItems([]);
  }, []);

  const totalItems = items.reduce((sum, it) => sum + it.quantity, 0);

  const value: CartContextValue = {
    items,
    totalItems,
    addItem,
    increment,
    decrement,
    getItemQuantity,
    clearCart,
  };

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
};

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) {
    throw new Error('useCart must be used within CartContextProvider');
  }
  return ctx;
}
