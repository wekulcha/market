import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MiniAppShell } from '../../layout/MiniAppShell';
import { Header } from '../../layout/Header';
import { useCart } from '../../context/CartContext';
import { CartItemRow } from '../../components/cart/CartItemRow';
import { MARKET_MIN_ORDER_TOTAL } from '../../config/market';
import { useAppContext } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { logUserActivity } from '../../api/activity';
import { deliveryCutoffHint, deliveryPromiseText } from '../../utils/deliveryPromise';

export function CartPage() {
  const navigate = useNavigate();
  const { items } = useCart();
  const { selectedRestaurant } = useAppContext();
  const { authReady, currentUser } = useAuth();

  const itemsTotal = items.reduce(
    (sum, item) => sum + item.meal.price * item.quantity,
    0
  );
  const missingToMinimum = Math.max(0, MARKET_MIN_ORDER_TOTAL - itemsTotal);
  const canCheckout = items.length > 0 && missingToMinimum === 0;

  useEffect(() => {
    if (!authReady || !currentUser) return;
    logUserActivity('cart_open', { itemsCount: items.length, itemsTotal });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authReady, currentUser?.id]);

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
            {deliveryPromiseText(selectedRestaurant?.ordersAcceptTo)}. {deliveryCutoffHint(selectedRestaurant?.ordersAcceptTo)}
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
            {missingToMinimum > 0 && (
              <div className="rounded-2xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                Минимальная сумма заказа — {MARKET_MIN_ORDER_TOTAL} ₽. Добавьте товаров ещё на {missingToMinimum.toFixed(0)} ₽.
              </div>
            )}
          </>
        )}
      </div>

      {/* "ДАЛЕЕ" button */}
      {items.length > 0 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 w-full max-w-[430px] px-4 z-20">
          <button
            disabled={!canCheckout}
            onClick={() => {
              if (canCheckout) navigate('/checkout', { replace: true });
            }}
            className={
              'w-full text-sm font-semibold py-3 rounded-2xl shadow-lg transition-colors ' +
              (canCheckout
                ? 'bg-slate-900 text-white hover:bg-slate-800'
                : 'bg-slate-300 text-slate-500 cursor-not-allowed')
            }
          >
            {canCheckout ? 'ДАЛЕЕ' : `МИНИМУМ ${MARKET_MIN_ORDER_TOTAL} ₽`}
          </button>
        </div>
      )}
    </MiniAppShell>
  );
}
