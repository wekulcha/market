import type { Meal } from '../../types/meal';
import { mealImageUrl } from '../../utils/mealImageUrl';
import { useCart } from '../../context/CartContext';

interface MealDetailModalProps {
  meal: Meal;
  onClose: () => void;
}

export function MealDetailModal({ meal, onClose }: MealDetailModalProps) {
  const { getItemQuantity, addItem, increment, decrement } = useCart();
  const quantity = getItemQuantity(meal.id);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/50"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="bg-white rounded-t-3xl sm:rounded-3xl w-full max-w-md max-h-[90vh] overflow-y-auto shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relative">
          <button
            type="button"
            onClick={onClose}
            className="absolute top-3 right-3 z-10 w-9 h-9 rounded-full bg-black/40 text-white flex items-center justify-center text-lg leading-none hover:bg-black/55"
            aria-label="Закрыть"
          >
            ×
          </button>
          <div className="aspect-[4/3] w-full bg-slate-100 overflow-hidden rounded-t-3xl sm:rounded-t-3xl">
            {meal.image_link ? (
              <img src={mealImageUrl(meal.image_link)} alt="" className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-slate-400 text-sm">Нет фото</div>
            )}
          </div>
        </div>
        <div className="p-4 space-y-3 pb-8">
          <h2 className="text-lg font-semibold text-slate-900 pr-10">{meal.name}</h2>
          {meal.description && <p className="text-sm text-slate-600">{meal.description}</p>}
          <div className="flex flex-wrap gap-3 text-xs text-slate-500">
            {meal.weight != null && <span>{meal.weight} г</span>}
            {meal.calorie != null && <span>{meal.calorie} ккал</span>}
          </div>
          <div>
            <div className="text-xl font-bold text-slate-900">
              {meal.price} ₽{meal.requires_final_weight ? '/кг' : ''}
            </div>
            {meal.requires_final_weight && (
              <div className="text-xs text-amber-700">
                Итоговая сумма обновится после взвешивания.
              </div>
            )}
          </div>
          <div className="flex justify-end pt-2">
            {quantity === 0 ? (
              <button
                type="button"
                onClick={() => addItem(meal)}
                className="bg-slate-900 text-white text-sm font-semibold py-2.5 px-8 rounded-full hover:bg-slate-800"
              >
                + Добавить
              </button>
            ) : (
              <div className="flex items-center gap-4 bg-slate-900 text-white rounded-full px-4 py-2">
                <button
                  type="button"
                  onClick={() => decrement(meal.id)}
                  className="text-lg font-medium w-8 text-center hover:opacity-80"
                >
                  −
                </button>
                <span className="text-sm min-w-[1.5rem] text-center font-semibold">{quantity}</span>
                <button
                  type="button"
                  onClick={() => increment(meal.id)}
                  className="text-lg font-medium w-8 text-center hover:opacity-80"
                >
                  +
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
