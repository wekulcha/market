import React, { useEffect, useMemo, useState } from "react";
import {
  AnalyticsPeriod,
  AdminAnalyticsSummary,
  AdminAnalyticsDailySeries,
} from "../../types/adminAnalytics";
import type { AdminOrder } from "../../types/adminOrder";
import {
  fetchAnalyticsSummary,
  fetchAnalyticsDaily,
} from "../../api/adminAnalytics";
import {
  fetchAdminOrders,
  fetchOrderPositions,
  fetchUser,
  patchOrderPaid,
} from "../../api/adminOrders";

interface AdminAnalyticsTabProps {
  restaurantId: number;
}

function formatCurrency(value: number): string {
  if (!Number.isFinite(value)) return "0 ₽";
  return `${Math.round(value)} ₽`;
}

function formatDateLabel(iso: string): string {
  const d = new Date(iso);
  const day = d.getDate().toString().padStart(2, "0");
  const month = (d.getMonth() + 1).toString().padStart(2, "0");
  return `${day}.${month}`;
}

interface AnalyticsSummaryCardsProps {
  summary: AdminAnalyticsSummary;
}

const AnalyticsSummaryCards: React.FC<AnalyticsSummaryCardsProps> = ({
  summary,
}) => {
  const {
    revenue,
    orders_count,
    avg_check,
    delivery_orders,
    dine_in_orders,
    paid_orders_count,
    unpaid_orders_count,
    paid_revenue,
    unpaid_revenue,
  } = summary;

  const totalOrders = orders_count || 1;
  const deliveryShare = Math.round((delivery_orders / totalOrders) * 100);
  const dineInShare = Math.round((dine_in_orders / totalOrders) * 100);

  return (
    <div className="grid justify-start gap-2 [grid-template-columns:repeat(auto-fit,minmax(190px,220px))]">
      {/* Revenue */}
      <div className="bg-emerald-50 rounded-2xl p-3 border border-emerald-100 shadow-sm flex flex-col gap-1">
        <div className="text-[10px] text-emerald-700 uppercase font-semibold">
          Выручка
        </div>
        <div className="text-sm font-bold text-emerald-900">
          {formatCurrency(revenue)}
        </div>
        <div className="text-[10px] text-emerald-700">
          за выбранный период
        </div>
      </div>

      {/* Orders */}
      <div className="bg-sky-50 rounded-2xl p-3 border border-sky-100 shadow-sm flex flex-col gap-1">
        <div className="text-[10px] text-sky-700 uppercase font-semibold">
          Заказы
        </div>
        <div className="text-sm font-bold text-sky-900">{orders_count}</div>
        <div className="text-[10px] text-sky-700">всего заказов</div>
      </div>

      {/* Average check */}
      <div className="bg-violet-50 rounded-2xl p-3 border border-violet-100 shadow-sm flex flex-col gap-1">
        <div className="text-[10px] text-violet-700 uppercase font-semibold">
          Средний чек
        </div>
        <div className="text-sm font-bold text-violet-900">
          {formatCurrency(avg_check)}
        </div>
        <div className="text-[10px] text-violet-700">выручка / заказы</div>
      </div>

      {/* Delivery vs Dine-in */}
      <div className="bg-amber-50 rounded-2xl p-3 border border-amber-100 shadow-sm flex flex-col gap-1">
        <div className="text-[10px] text-amber-700 uppercase font-semibold">
          Формат
        </div>
        <div className="flex items-center justify-between text-[10px] text-amber-800">
          <div>
            Доставка:{" "}
            <span className="font-semibold">
              {delivery_orders} ({deliveryShare}%)
            </span>
          </div>
          <div>
            На месте:{" "}
            <span className="font-semibold">
              {dine_in_orders} ({dineInShare}%)
            </span>
          </div>
        </div>
        <div className="h-2 rounded-full bg-amber-100 overflow-hidden mt-1">
          <div
            className="h-full bg-amber-400"
            style={{ width: `${deliveryShare}%` }}
          />
        </div>
      </div>

      <div className="bg-emerald-50 rounded-2xl p-3 border border-emerald-100 shadow-sm flex flex-col gap-1 col-span-2">
        <div className="text-[10px] text-emerald-700 uppercase font-semibold">
          Оплата (отмечено в панели)
        </div>
        <div className="flex flex-wrap gap-2 text-[11px] text-emerald-900">
          <span>
            Оплачено: <b>{paid_orders_count}</b> · {formatCurrency(paid_revenue)}
          </span>
          <span className="text-emerald-600">·</span>
          <span>
            Не отмечено: <b>{unpaid_orders_count}</b> · {formatCurrency(unpaid_revenue)}
          </span>
        </div>
      </div>
    </div>
  );
};

interface AnalyticsDailyChartProps {
  daily: AdminAnalyticsDailySeries | null;
  maxRevenue: number;
}

const AnalyticsDailyChart: React.FC<AnalyticsDailyChartProps> = ({
  daily,
  maxRevenue,
}) => {
  const points = daily?.points ?? [];
  if (!points.length) {
    return (
      <div className="bg-white rounded-3xl p-3 border border-slate-100 shadow-sm text-xs text-slate-500">
        Пока нет данных для графика.
      </div>
    );
  }

  const safeMax = maxRevenue > 0 ? maxRevenue : 1;

  return (
    <div className="bg-white rounded-3xl p-3 border border-slate-100 shadow-sm space-y-2">
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs font-semibold text-slate-900">
          Динамика выручки
        </div>
        <div className="text-[10px] text-slate-500">по дням</div>
      </div>

      <div className="flex items-end gap-1 h-28">
        {points.map((p) => {
          const heightPercent = Math.max(
            8,
            Math.round((p.revenue / safeMax) * 100)
          );
          return (
            <div
              key={p.date}
              className="flex-1 flex flex-col items-center gap-1"
            >
              <div className="flex-1 flex items-end w-full">
                <div
                  className="w-full rounded-full bg-slate-100 overflow-hidden"
                  style={{ height: "100%" }}
                >
                  <div
                    className="w-full rounded-full bg-slate-900"
                    style={{ height: `${heightPercent}%` }}
                  />
                </div>
              </div>
              <div className="text-[9px] text-slate-500">
                {formatDateLabel(p.date)}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex justify-between text-[10px] text-slate-500 mt-1">
        <span>Минимум: {formatCurrency(0)}</span>
        <span>Максимум: {formatCurrency(safeMax)}</span>
      </div>
    </div>
  );
};

const STATUS_LABEL: Record<string, string> = {
  CREATED: "Принят",
  ACCEPTED: "Собран",
  COOKING: "Собран",
  DELIVERY: "Собран",
  DONE: "Завершён",
  CANCELLED: "Отменён",
};

export const AdminAnalyticsTab: React.FC<AdminAnalyticsTabProps> = ({
  restaurantId,
}) => {
  const [period, setPeriod] = useState<AnalyticsPeriod>("today");
  const [view, setView] = useState<"dashboard" | "today_orders">("dashboard");
  const [summary, setSummary] = useState<AdminAnalyticsSummary | null>(null);
  const [daily, setDaily] = useState<AdminAnalyticsDailySeries | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [todayOrders, setTodayOrders] = useState<AdminOrder[]>([]);
  const [todayLoading, setTodayLoading] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<AdminOrder | null>(null);

  useEffect(() => {
    if (!restaurantId || Number.isNaN(restaurantId)) return;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const [s, d] = await Promise.all([
          fetchAnalyticsSummary(restaurantId, period),
          fetchAnalyticsDaily(restaurantId, period),
        ]);
        setSummary(s);
        setDaily(d);
      } catch (err) {
        console.error(err);
        setError("Не удалось загрузить аналитику. Попробуйте позже.");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [restaurantId, period]);

  useEffect(() => {
    if (!restaurantId || Number.isNaN(restaurantId) || view !== "today_orders") return;
    let cancelled = false;
    const loadToday = async () => {
      try {
        setTodayLoading(true);
        const data = await fetchAdminOrders(restaurantId, "ALL", { todayOnly: true });
        if (!cancelled) setTodayOrders(data);
      } catch (e) {
        console.error(e);
        if (!cancelled) setTodayOrders([]);
      } finally {
        if (!cancelled) setTodayLoading(false);
      }
    };
    void loadToday();
    const id = window.setInterval(loadToday, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [restaurantId, view]);

  const chartPoints = daily?.points ?? [];
  const maxRevenue = useMemo(() => {
    if (!chartPoints.length) return 0;
    return Math.max(...chartPoints.map((p) => p.revenue));
  }, [chartPoints]);

  const periodOptions: { key: AnalyticsPeriod; label: string }[] = [
    { key: "today", label: "Сегодня" },
    { key: "7d", label: "7 дней" },
    { key: "30d", label: "30 дней" },
  ];

  return (
    <div className="space-y-3">
      {/* Header & period switch */}
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-900">
          Аналитика заказов
        </div>
      </div>

      <div className="flex gap-1 overflow-x-auto no-scrollbar pb-1">
        <button
          type="button"
          onClick={() => setView("dashboard")}
          className={
            "px-3 py-1.5 rounded-full text-[11px] font-medium border transition-colors whitespace-nowrap " +
            (view === "dashboard"
              ? "bg-slate-900 text-white border-slate-900"
              : "bg-slate-50 text-slate-700 border-slate-200")
          }
        >
          Сводка
        </button>
        <button
          type="button"
          onClick={() => setView("today_orders")}
          className={
            "px-3 py-1.5 rounded-full text-[11px] font-medium border transition-colors whitespace-nowrap " +
            (view === "today_orders"
              ? "bg-slate-900 text-white border-slate-900"
              : "bg-slate-50 text-slate-700 border-slate-200")
          }
        >
          Заказы сегодня
        </button>
      </div>

      {view === "dashboard" && (
        <div className="flex gap-1 overflow-x-auto no-scrollbar pb-1">
          {periodOptions.map((p) => {
            const isActive = period === p.key;
            return (
              <button
                key={p.key}
                type="button"
                onClick={() => setPeriod(p.key)}
                className={
                  "px-3 py-1.5 rounded-full text-[11px] font-medium border transition-colors whitespace-nowrap " +
                  (isActive
                    ? "bg-slate-900 text-white border-slate-900"
                    : "bg-slate-50 text-slate-700 border-slate-200")
                }
              >
                {p.label}
              </button>
            );
          })}
        </div>
      )}

      {/* Loading / Error */}
      {view === "dashboard" && loading && (
        <div className="text-xs text-slate-500">Загрузка аналитики…</div>
      )}

      {view === "dashboard" && error && !loading && (
        <div className="text-xs text-red-500">{error}</div>
      )}

      {/* Content */}
      {view === "dashboard" && !loading && !error && summary && (
        <>
          <AnalyticsSummaryCards summary={summary} />
          <AnalyticsDailyChart daily={daily} maxRevenue={maxRevenue} />
        </>
      )}

      {view === "today_orders" && (
        <div className="space-y-2">
          <div className="text-[11px] text-slate-500">
            Заказы за сегодня (по Москве). Нажмите строку для подробностей.
          </div>
          {todayLoading && (
            <div className="text-xs text-slate-500">Загрузка…</div>
          )}
          {!todayLoading && todayOrders.length === 0 && (
            <div className="text-xs text-slate-500">Пока нет заказов за сегодня.</div>
          )}
          <div className="rounded-2xl border border-slate-100 overflow-hidden bg-white">
            {todayOrders.map((o) => (
              <button
                key={o.id}
                type="button"
                onClick={() => setSelectedOrder(o)}
                className="w-full flex items-center gap-2 px-3 py-2 border-b border-slate-50 last:border-0 text-left hover:bg-slate-50"
              >
                <span className="text-[11px] font-semibold text-slate-900 w-14 shrink-0">
                  №{o.id}
                </span>
                <span className="text-[11px] text-slate-700 flex-1 min-w-0 truncate">
                  {STATUS_LABEL[o.status] ?? o.status}
                </span>
                <span className="text-[11px] font-semibold text-slate-900 w-16 text-right shrink-0">
                  {Math.round(o.total)} ₽
                </span>
                <span className="text-sm w-6 text-center shrink-0" title={o.isPaid ? "Оплачено" : "Не отмечено оплаченным"}>
                  {o.isPaid ? "🟢" : "🔴"}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {selectedOrder && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center px-4"
          onClick={() => setSelectedOrder(null)}
        >
          <div
            className="bg-white rounded-3xl p-4 w-full max-w-xl shadow-lg space-y-3 max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <TodayOrderDetailBody
              order={selectedOrder}
              onClose={() => setSelectedOrder(null)}
              onTogglePaid={async () => {
                try {
                  const u = await patchOrderPaid(selectedOrder.id, !selectedOrder.isPaid);
                  setTodayOrders((prev) => prev.map((x) => (x.id === u.id ? u : x)));
                  setSelectedOrder(u);
                } catch {
                  alert("Не удалось обновить оплату");
                }
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

function TodayOrderDetailBody({
  order,
  onClose,
  onTogglePaid,
}: {
  order: AdminOrder;
  onClose: () => void;
  onTogglePaid: () => void | Promise<void>;
}) {
  const [items, setItems] = useState<{ meal_id: number; name: string; quantity: number }[]>([]);
  const [userInfo, setUserInfo] = useState<{ username: string; phone: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const [positions, user] = await Promise.all([
          fetchOrderPositions(order.id),
          fetchUser(order.userId),
        ]);
        if (!cancelled) {
          setItems(positions);
          setUserInfo(user);
        }
      } catch {
        if (!cancelled) setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [order.id, order.userId]);

  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-xs text-slate-500">Заказ</div>
          <div className="text-sm font-bold text-slate-900">№{order.id}</div>
        </div>
        <button type="button" className="text-slate-400 hover:text-slate-700 text-lg leading-none" onClick={onClose}>
          ×
        </button>
      </div>
      <div className="text-[11px] text-slate-600">
        {STATUS_LABEL[order.status] ?? order.status} · {Math.round(order.total)} ₽
      </div>
      {order.status === "DONE" && (
        <button
          type="button"
          onClick={() => void onTogglePaid()}
          className="w-full rounded-xl border border-slate-200 py-2 text-[11px] font-medium text-slate-800"
        >
          {order.isPaid ? "✓ Оплачено (нажмите, чтобы снять)" : "Отметить как оплачено"}
        </button>
      )}
      <div className="space-y-1">
        <div className="text-[11px] font-semibold text-slate-700">Клиент</div>
        {loading ? (
          <div className="text-[11px] text-slate-500">Загрузка...</div>
        ) : (
          <>
            <div className="text-[11px] text-slate-600">
              {userInfo?.username ? `@${userInfo.username}` : "—"}
            </div>
            <div className="text-[11px] text-slate-600">{userInfo?.phone ?? "—"}</div>
          </>
        )}
      </div>
      <div className="space-y-1">
        <div className="text-[11px] font-semibold text-slate-700">Позиции</div>
        <div className="space-y-1 max-h-40 overflow-auto">
          {loading ? (
            <div className="text-[11px] text-slate-500">Загрузка...</div>
          ) : (
            items.map((item) => (
              <div key={`${item.meal_id}-${item.quantity}`} className="flex justify-between text-xs text-slate-700">
                <span className="truncate">{item.name}</span>
                <span className="text-slate-500">×{item.quantity}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
