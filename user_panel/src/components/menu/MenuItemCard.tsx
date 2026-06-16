import { useState } from 'react';
import { useCart } from '../../context/CartContext';
import type { Meal } from '../../types/meal';
import { mealImageUrl } from '../../utils/mealImageUrl';
import { MealDetailModal } from './MealDetailModal';

interface MenuItemCardProps {
  meal: Meal;
}

export function MenuItemCard({ meal }: MenuItemCardProps) {
  const { getItemQuantity, addItem, increment, decrement } = useCart();
  const quantity = getItemQuantity(meal.id);
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="bg-white rounded-2xl shadow-sm p-3 flex gap-3 w-full text-left"
      >
        <div className="w-20 h-20 rounded-xl overflow-hidden flex-shrink-0 pointer-events-none">
          {meal.image_link ? (
            <img src={mealImageUrl(meal.image_link)} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full bg-slate-100" />
          )}
        </div>

        <div className="flex-1 flex gap-3 min-w-0">
          <div className="flex-1 min-w-0 flex flex-col min-h-[5rem]">
            <h3 className="text-sm font-semibold text-slate-900 line-clamp-2">{meal.name}</h3>
            {meal.description && (
              <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{meal.description}</p>
            )}
            {meal.weight != null && (
              <p className="text-xs text-slate-400 mt-auto">{meal.weight} г</p>
            )}
          </div>

          <div
            className="flex flex-col items-end justify-between shrink-0 w-[100px]"
            onClick={(e) => e.stopPropagation()}
          >
            <span className="text-sm font-bold text-slate-900">
              {meal.price} ₽{meal.requires_final_weight ? '/кг' : ''}
            </span>
            {meal.requires_final_weight && (
              <span className="text-[10px] text-amber-600 text-right leading-tight">
                итог после взвешивания
              </span>
            )}
            {quantity === 0 ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  addItem(meal);
                }}
                className="bg-slate-900 text-white text-xs font-medium py-1.5 px-3 rounded-full hover:bg-slate-800 w-full max-w-[100px]"
              >
                + Добавить
              </button>
            ) : (
              <div className="flex items-center gap-2 bg-slate-900 text-white rounded-full px-2 py-1">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    decrement(meal.id);
                  }}
                  className="text-sm w-6 text-center"
                >
                  −
                </button>
                <span className="text-xs min-w-[1rem] text-center">{quantity}</span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    increment(meal.id);
                  }}
                  className="text-sm w-6 text-center"
                >
                  +
                </button>
              </div>
            )}
          </div>
        </div>
      </button>

      {open && <MealDetailModal meal={meal} onClose={() => setOpen(false)} />}
    </>
  );
}
