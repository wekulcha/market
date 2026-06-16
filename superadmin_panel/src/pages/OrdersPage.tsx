import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchAdminOrderDetail, fetchAdminOrders } from "../api/admin";
import type { AdminOrderDetail, AdminOrderSummary } from "../types/admin";

function formatMoney(v: number | string | undefined): string {
  if (v === undefined) return "—";
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? `${n.toFixed(0)} ₽` : "—";
}

function formatWhen(iso: string | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

const STATUS_RU: Record<string, string> = {
  CREATED: "Принят",
  ACCEPTED: "Собран",
  COOKING: "Собран",
  DELIVERY: "Собран",
  DONE: "Завершён",
  CANCELLED: "Отменён",
};

export function OrdersPage() {
  const [openId, setOpenId] = useState<number | null>(null);
  const [orderQ, setOrderQ] = useState("");

  const { data: orders = [], isLoading, error } = useQuery({
    queryKey: ["admin", "orders", orderQ],
    queryFn: () => fetchAdminOrders(orderQ),
  });

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ["admin", "orders", openId],
    queryFn: () => fetchAdminOrderDetail(openId!),
    enabled: openId != null,
  });

  const list = orders as AdminOrderSummary[];

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <h1 className="text-xl font-semibold text-slate-900">Заказы</h1>
        <input
          type="search"
          placeholder="№ заказа, ID магазина или пользователя, название магазина…"
          value={orderQ}
          onChange={(e) => setOrderQ(e.target.value)}
          className="w-full sm:max-w-md rounded-xl border border-slate-200 px-3 py-2 text-sm"
        />
      </div>
      {isLoading && <p className="text-sm text-slate-500">Загрузка…</p>}
      {error && <p className="text-sm text-red-600">{String(error)}</p>}
      <div className="grid gap-2">
        {list.map((o) => (
          <button
            key={o.id}
            type="button"
            onClick={() => setOpenId(o.id)}
            className="bg-white rounded-2xl px-3 py-2.5 shadow-sm border border-slate-100 text-left hover:border-slate-200 transition-colors flex items-center justify-between gap-3"
          >
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-900">№{o.id}</div>
              <div className="text-[11px] text-slate-500 truncate">{o.restaurantName}</div>
              <div className="text-[10px] text-slate-400 mt-0.5">{formatWhen(o.createdAt)}</div>
            </div>
            <div className="text-right shrink-0">
              <div className="text-sm font-semibold text-slate-900">{formatMoney(o.total)}</div>
              <div className="text-[10px] text-slate-500">{STATUS_RU[o.status] ?? o.status}</div>
            </div>
          </button>
        ))}
      </div>

      {openId != null && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center p-4"
          onClick={() => setOpenId(null)}
        >
          <div
            className="bg-white rounded-3xl p-4 w-full max-w-md max-h-[88vh] overflow-y-auto shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start gap-2 mb-3">
              <div className="text-sm font-semibold text-slate-900">Заказ №{openId}</div>
              <button
                type="button"
                className="text-slate-400 hover:text-slate-700 text-lg leading-none"
                onClick={() => setOpenId(null)}
              >
                ×
              </button>
            </div>
            {detailLoading && <p className="text-xs text-slate-500">Загрузка…</p>}
            {detail && <OrderDetailBody d={detail} />}
          </div>
        </div>
      )}
    </div>
  );
}

function OrderDetailBody({ d }: { d: AdminOrderDetail }) {
  return (
    <div className="text-xs text-slate-700 space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <div className="text-[10px] text-slate-400 uppercase">Статус</div>
          <div>{STATUS_RU[d.status] ?? d.status}</div>
        </div>
        <div>
          <div className="text-[10px] text-slate-400 uppercase">Сумма</div>
          <div className="font-semibold">{formatMoney(d.total)}</div>
        </div>
        <div className="col-span-2">
          <div className="text-[10px] text-slate-400 uppercase">Время</div>
          <div>{formatWhen(d.createdAt)}</div>
        </div>
        <div className="col-span-2">
          <div className="text-[10px] text-slate-400 uppercase">Магазин</div>
          <div>{d.restaurantName}</div>
        </div>
        <div className="col-span-2">
          <div className="text-[10px] text-slate-400 uppercase">Заказчик</div>
          <div>
            {d.username ? `@${d.username.replace(/^@/, "")}` : "—"} · {d.phone ?? "—"}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">user id: {d.userId}</div>
        </div>
        {d.deliveryAddress && (
          <div className="col-span-2">
            <div className="text-[10px] text-slate-400 uppercase">Локация / адрес</div>
            <div>{d.deliveryAddress}</div>
          </div>
        )}
        {d.tableNumber && (
          <div className="col-span-2">
            <div className="text-[10px] text-slate-400 uppercase">Место</div>
            <div>{d.tableNumber}</div>
          </div>
        )}
        <div>
          <div className="text-[10px] text-slate-400 uppercase">Тип</div>
          <div>{d.orderType === "DELIVERY" ? "Доставка" : "На месте"}</div>
        </div>
      </div>
      <div>
        <div className="text-[10px] font-semibold text-slate-500 uppercase mb-1">Позиции</div>
        <ul className="space-y-1.5 border border-slate-100 rounded-xl p-2 bg-slate-50/80">
          {d.positions.map((p, i) => (
            <li key={i} className="flex justify-between gap-2">
              <span className="text-slate-800">
                {p.mealName} ×{p.quantity}{p.mealWeight ? ` (${p.mealWeight} г)` : ""}
              </span>
              <span className="text-slate-600 shrink-0">{formatMoney(p.totalPrice)}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="flex justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-100">
        <span>Товары</span>
        <span>{formatMoney(d.itemsTotal)}</span>
      </div>
      <div className="flex justify-between text-[11px] text-slate-500">
        <span>Доставка / сервис</span>
        <span>
          {formatMoney(d.deliveryFee)} / {formatMoney(d.serviceFee)}
        </span>
      </div>
    </div>
  );
}
