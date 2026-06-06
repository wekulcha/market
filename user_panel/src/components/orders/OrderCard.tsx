import { useState } from 'react';
import type { OrderStatus, UserOrder } from '../../types/order';
import { cancelOrder } from '../../api/orders';

const STATUS_LABELS: Record<OrderStatus, string> = {
  CREATED: 'Создан',
  ACCEPTED: 'Принят',
  COOKING: 'Готовится',
  DELIVERY: 'В доставке',
  DONE: 'Завершен',
  CANCELLED: 'Отменен',
};

const ORDER_TYPE_LABELS = {
  DELIVERY: 'Доставка',
  DINE_IN: 'На месте',
} as const;

function formatDate(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
}

function formatMoney(value: number | null): string {
  if (value == null) return '—';
  return `${value.toFixed(0)} ₽`;
}

export function OrderCard({
  order,
  onChanged,
}: {
  order: UserOrder;
  onChanged?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const canCancel = order.status === 'CREATED';

  const handleCancel = async () => {
    if (!canCancel || busy) return;
    if (!confirm('Отменить заказ?')) return;
    setErr(null);
    setBusy(true);
    try {
      await cancelOrder(order.id);
      onChanged?.();
    } catch {
      setErr('Не удалось отменить.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-3 space-y-1">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-slate-900">Заказ №{order.id}</div>
        <div className="text-xs text-slate-500">{STATUS_LABELS[order.status]}</div>
      </div>
      <div className="text-xs text-slate-500">{formatDate(order.created_at)}</div>
      <div className="flex items-center justify-between gap-3 text-sm text-slate-700">
        <span>{order.order_type ? ORDER_TYPE_LABELS[order.order_type] : '—'}</span>
        <span className="font-semibold text-slate-900">{formatMoney(order.total)}</span>
      </div>
      {order.delivery_address && (
        <div className="text-xs text-slate-500">Адрес: {order.delivery_address}</div>
      )}
      {err && <div className="text-xs text-red-600">{err}</div>}
      {canCancel && (
        <button
          type="button"
          disabled={busy}
          onClick={() => void handleCancel()}
          className="mt-2 w-full rounded-xl border border-rose-200 bg-white py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50"
        >
          {busy ? 'Отмена…' : 'Отменить заказ'}
        </button>
      )}
    </div>
  );
}
