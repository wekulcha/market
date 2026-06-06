import { useCart } from '../../context/CartContext';
import type { CartItem } from '../../types/cart';
import { mealImageUrl } from '../../utils/mealImageUrl';

interface CartItemRowProps {
  item: CartItem;
}

export function CartItemRow({ item }: CartItemRowProps) {
  const { increment, decrement } = useCart();
  const positionTotal = item.meal.price * item.quantity;

  return (
    <div className="flex gap-3 items-center bg-white rounded-2xl p-3 shadow-sm">
      {/* Image */}
      <div className="w-16 h-16 rounded-xl overflow-hidden flex-shrink-0">
        {item.meal.image_link ? (
          <img
            src={mealImageUrl(item.meal.image_link)}
            alt={item.meal.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full bg-slate-100"></div>
        )}
      </div>

      {/* Middle content */}
      <div className="flex-1 min-w-0">
        {/* Name */}
        <h3 className="text-sm font-semibold text-slate-900 mb-1 line-clamp-2">
          {item.meal.name}
        </h3>

        {/* Price and weight */}
        <p className="text-xs text-slate-500 mb-1">
          {item.meal.price} ₽{item.meal.weight ? ` · ${item.meal.weight} г` : ''}
        </p>

        {/* Position total */}
        <p className="text-xs text-slate-700 font-medium">
          Сумма: {positionTotal.toFixed(0)} ₽
        </p>
      </div>

      {/* Quantity control */}
      <div className="flex items-center gap-3 bg-slate-900 text-white rounded-full px-3 py-1 flex-shrink-0">
        <button
          onClick={() => decrement(item.meal.id)}
          className="text-lg leading-none hover:opacity-80 transition-opacity"
        >
          -
        </button>
        <span className="text-sm min-w-[1.5rem] text-center">{item.quantity}</span>
        <button
          onClick={() => increment(item.meal.id)}
          className="text-lg leading-none hover:opacity-80 transition-opacity"
        >
          +
        </button>
      </div>
    </div>
  );
}

