import { useNavigate } from 'react-router-dom';
import { MiniAppShell } from '../../layout/MiniAppShell';
import { Header } from '../../layout/Header';
import { useCart } from '../../context/CartContext';
import { CartItemRow } from '../../components/cart/CartItemRow';

export function CartPage() {
  const navigate = useNavigate();
  const { items } = useCart();

  const itemsTotal = items.reduce(
    (sum, item) => sum + item.meal.price * item.quantity,
    0
  );

  return (
    <MiniAppShell>
      <div className="space-y-4 pb-24">
        <Header
          title="Корзина"
          showBack
          onBackClick={() => navigate(-1)}
          onProfileClick={() => navigate('/profile')}
          showSearch={false}
        />

        {/* Service type block */}
        <div className="bg-slate-100 rounded-2xl px-4 py-3 text-sm text-slate-700 flex flex-col gap-1">
          <div className="font-semibold">Доставка</div>
          <div className="text-xs text-slate-500">
            Адрес доставки будет указан на следующем шаге.
          </div>
        </div>

        {/* Cart items list */}
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-center text-sm text-slate-500 mt-8">
            <p>Ваша корзина пуста.</p>
            <button
              onClick={() => navigate('/catalog')}
              className="mt-3 text-xs font-medium text-slate-900 underline hover:text-slate-700"
            >
              Перейти в каталог
            </button>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              {items.map((item) => (
                <CartItemRow key={item.meal.id} item={item} />
              ))}
            </div>

            {/* Total sum */}
            <div className="flex justify-end mt-2">
              <div className="text-sm text-slate-700">
                Итого за товары:{' '}
                <span className="font-semibold">{itemsTotal.toFixed(0)} ₽</span>
              </div>
            </div>
          </>
        )}
      </div>

      {/* "ДАЛЕЕ" button */}
      {items.length > 0 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 w-full max-w-[430px] px-4 z-20">
          <button
            onClick={() => navigate('/checkout', { replace: true })}
            className="w-full bg-slate-900 text-white text-sm font-semibold py-3 rounded-2xl shadow-lg hover:bg-slate-800 transition-colors"
          >
            ДАЛЕЕ
          </button>
        </div>
      )}
    </MiniAppShell>
  );
}
