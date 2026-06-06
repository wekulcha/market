import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchMyOrders, fetchOrderPositionsForUser } from '../../api/orders';
import { OrderCard } from '../../components/orders/OrderCard';
import { useAuth } from '../../context/AuthContext';
import { Header } from '../../layout/Header';
import { MiniAppShell } from '../../layout/MiniAppShell';
import type { OrderStatus, UserOrder } from '../../types/order';

const ACTIVE_STATUSES = new Set<OrderStatus>(['CREATED', 'ACCEPTED', 'COOKING', 'DELIVERY']);

export function OrderHistoryPage() {
  const navigate = useNavigate();
  const { currentUser, authReady } = useAuth();
  const [orders, setOrders] = useState<UserOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<UserOrder | null>(null);

  useEffect(() => {
    if (!authReady || !currentUser) {
      setOrders([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    void fetchMyOrders()
      .then((list) => {
        if (!cancelled) setOrders(list);
      })
      .catch(() => {
        if (!cancelled) {
          setOrders([]);
          setError('Не удалось загрузить историю заказов.');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [authReady, currentUser]);

  const pastOrders = useMemo(
    () => orders.filter((order) => !ACTIVE_STATUSES.has(order.status)),
    [orders]
  );

  return (
    <MiniAppShell>
      <Header
        title="История заказов"
        showSearch={false}
        showBack
        onBackClick={() => navigate(-1)}
        onHomeClick={() => navigate('/catalog')}
      />
      <main className="mt-4 space-y-3 pb-20">
        {!authReady && (
          <div className="text-sm text-slate-600">Проверяем вход в Telegram…</div>
        )}
        {authReady && !currentUser && (
          <div className="text-sm text-amber-800 bg-amber-50 rounded-xl p-3">
            Войдите в аккаунт, чтобы видеть историю.
          </div>
        )}
        {currentUser && loading && (
          <div className="text-xs text-slate-500">Загрузка…</div>
        )}
        {error && <div className="text-xs text-amber-600">{error}</div>}
        {currentUser && !loading && pastOrders.length === 0 && !error && (
          <div className="text-sm text-slate-500">Пока завершённых заказов нет.</div>
        )}
        {pastOrders.length > 0 && (
          <div className="space-y-2">
            {pastOrders.map((order) => (
              <button
                key={order.id}
                type="button"
                className="w-full text-left"
                onClick={() => setSelected(order)}
              >
                <OrderCard order={order} />
              </button>
            ))}
          </div>
        )}
      </main>
      {selected && (
        <OrderDetailsModal order={selected} onClose={() => setSelected(null)} />
      )}
    </MiniAppShell>
  );
}

function OrderDetailsModal({ order, onClose }: { order: UserOrder; onClose: () => void }) {
  const [items, setItems] = useState<
    { meal_id: number; name: string; quantity: number; total_price: number }[]
  >([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const data = await fetchOrderPositionsForUser(order.id);
        if (!cancelled) setItems(data);
      } catch {
        if (!cancelled) setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [order.id]);

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center px-4" onClick={onClose}>
      <div
        className="bg-white rounded-3xl p-4 w-full max-w-sm shadow-lg space-y-3 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="text-xs text-slate-500">Заказ</div>
            <div className="text-sm font-bold text-slate-900">№{order.id}</div>
          </div>
          <button type="button" className="text-slate-400 text-lg leading-none" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="text-[11px] text-slate-600">
          {order.order_type === 'DINE_IN' ? 'На месте' : 'Доставка'} · {order.total ?? 0} ₽
        </div>
        {order.delivery_address && (
          <div className="text-[11px] text-slate-600">Адрес: {order.delivery_address}</div>
        )}
        {order.table_number && (
          <div className="text-[11px] text-slate-600">Место: {order.table_number}</div>
        )}
        {order.comment && <div className="text-[11px] text-slate-600">Комментарий: {order.comment}</div>}
        <div className="space-y-1">
          <div className="text-[11px] font-semibold text-slate-700">Позиции</div>
          <div className="space-y-1 max-h-44 overflow-auto">
            {loading ? (
              <div className="text-[11px] text-slate-500">Загрузка...</div>
            ) : (
              items.map((item) => (
                <div key={`${item.meal_id}-${item.quantity}`} className="flex justify-between text-xs text-slate-700">
                  <span className="truncate">{item.name}</span>
                  <span className="ml-2 text-slate-500">
                    ×{item.quantity} · {Math.round(item.total_price)} ₽
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
