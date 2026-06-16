import React, { useEffect, useState, useRef } from "react";
import type {
  AdminOrder,
  AdminOrderItem,
  AdminOrderStatusCode,
} from "../../types/adminOrder";
import {
  fetchAdminOrders,
  updateAdminOrderStatus,
  fetchOrderPositions,
  fetchUser,
  patchOrderPaid,
  patchOrderFinalWeights,
  AdminOrderFilterStatus,
} from "../../api/adminOrders";
import { printKitchenTicket } from "../../utils/printKitchenTicket";

const STATUS_FLOW: AdminOrderStatusCode[] = [
  "CREATED",
  "ACCEPTED",
  "DONE",
];

const STATUS_LABEL: Record<AdminOrderStatusCode, string> = {
  CREATED: "Принят",
  ACCEPTED: "Собран",
  COOKING: "Собран",
  DELIVERY: "Собран",
  DONE: "Завершён",
  CANCELLED: "Отменён",
};

const STATUS_COLOR_CLASSES: Record<AdminOrderStatusCode, string> = {
  CREATED: "bg-amber-50 text-amber-800 border-amber-200",
  ACCEPTED: "bg-sky-50 text-sky-800 border-sky-200",
  COOKING: "bg-sky-50 text-sky-800 border-sky-200",
  DELIVERY: "bg-sky-50 text-sky-800 border-sky-200",
  DONE: "bg-emerald-50 text-emerald-800 border-emerald-200",
  CANCELLED: "bg-rose-50 text-rose-800 border-rose-200",
};

const STATUS_PICKER_OPTIONS: AdminOrderStatusCode[] = [
  "CREATED",
  "ACCEPTED",
  "DONE",
  "CANCELLED",
];

interface AdminOrdersTabProps {
  restaurantId: number;
  restaurantName?: string;
  /** Главный экран магазина — без заголовка «Управление заказами». */
  hideTitle?: boolean;
}

function getNextStatus(
  current: AdminOrderStatusCode
): AdminOrderStatusCode | null {
  if (current === "COOKING" || current === "DELIVERY") return "DONE";
  const idx = STATUS_FLOW.indexOf(current);
  if (idx === -1 || idx === STATUS_FLOW.length - 1) return null;
  return STATUS_FLOW[idx + 1];
}

function formatTime(iso: string): string {
  const dt = new Date(iso);
  const hh = dt.getHours().toString().padStart(2, "0");
  const mm = dt.getMinutes().toString().padStart(2, "0");
  return `${hh}:${mm}`;
}

function formatDateTime(iso: string): string {
  const dt = new Date(iso);
  const day = dt.getDate().toString().padStart(2, "0");
  const month = (dt.getMonth() + 1).toString().padStart(2, "0");
  const year = dt.getFullYear();
  const hh = dt.getHours().toString().padStart(2, "0");
  const mm = dt.getMinutes().toString().padStart(2, "0");
  return `${day}.${month}.${year} ${hh}:${mm}`;
}

function statusPillClass(status: AdminOrderStatusCode): string {
  return (
    "inline-flex items-center gap-1 px-2 py-1 rounded-full border text-[9px] font-semibold whitespace-nowrap " +
    STATUS_COLOR_CLASSES[status]
  );
}

function statusLabel(status: AdminOrderStatusCode): string {
  return STATUS_LABEL[status];
}

function nextStatusLabel(status: AdminOrderStatusCode): string {
  const next = getNextStatus(status);
  return next ? STATUS_LABEL[next] : STATUS_LABEL[status];
}

function canPrintOrder(status: AdminOrderStatusCode): boolean {
  return status === "CREATED" || status === "ACCEPTED";
}

function placeLabel(order: AdminOrder): string {
  if (order.orderType === "DINE_IN") {
    return order.tableNumber ? `Место ${order.tableNumber}` : "На месте";
  }
  return order.deliveryAddress || "Без адреса";
}

function paidBadgeClass(isPaid: boolean): string {
  return isPaid
    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : "bg-rose-50 text-rose-700 border-rose-200";
}

function primaryActionLabel(order: AdminOrder): string {
  if (order.status === "DONE") {
    return order.isPaid ? "Заказ оплачен" : "Оплачен";
  }
  return nextStatusLabel(order.status);
}

function PrinterIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.8}
        d="M7 9V4h10v5m-9 8h8m-8 3h8m-9-7H6a2 2 0 01-2-2v-1a3 3 0 013-3h10a3 3 0 013 3v1a2 2 0 01-2 2h-1m-10 0v7h10v-7H7z"
      />
    </svg>
  );
}

interface OrderCardProps {
  order: AdminOrder;
  isUpdating: boolean;
  isPrinting: boolean;
  onChangeStatus: (newStatus: AdminOrderStatusCode) => Promise<void> | void;
  onPaidUpdated: (order: AdminOrder) => void;
  onOpenDetails: (order: AdminOrder) => void;
  onPrint: (order: AdminOrder) => Promise<void> | void;
}

const OrderCard: React.FC<OrderCardProps> = ({
  order,
  isUpdating,
  isPrinting,
  onChangeStatus,
  onPaidUpdated,
  onOpenDetails,
  onPrint,
}) => {
  const [statusPickerOpen, setStatusPickerOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);

  const nextStatus = getNextStatus(order.status);
  const printable = canPrintOrder(order.status);

  // Close picker when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        pickerRef.current &&
        !pickerRef.current.contains(event.target as Node)
      ) {
        setStatusPickerOpen(false);
      }
    };

    if (statusPickerOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [statusPickerOpen]);

  return (
    <div
      className="bg-white rounded-2xl p-3 border border-slate-100 shadow-sm flex flex-col gap-2.5 cursor-pointer"
      onClick={() => onOpenDetails(order)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-xs font-semibold text-slate-900">№{order.id}</div>
          <div className="mt-1 flex flex-col items-start gap-1">
            <span className={statusPillClass(order.status)}>
              <span className="w-1.5 h-1.5 rounded-full bg-current" />
              {statusLabel(order.status)}
            </span>
            <span
              className={
                "inline-flex items-center rounded-full border px-2 py-0.5 text-[9px] font-semibold " +
                paidBadgeClass(Boolean(order.isPaid))
              }
              title={order.isPaid ? "Оплачено" : "Не оплачено"}
            >
              {order.isPaid ? "Оплачен" : "Не оплачен"}
            </span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 text-right">
          <span className="text-[10px] text-slate-500">
            {formatTime(order.createdAt)}
          </span>
          <span className="text-[10px] text-slate-500">
            {order.orderType === "DINE_IN" ? "На месте" : "Доставка"}
          </span>
          <span className="text-sm font-bold text-slate-900">
            {Math.round(order.total)} ₽
          </span>
        </div>
      </div>

      <div className="rounded-xl bg-slate-50 px-2.5 py-2">
        <div
          className="text-[11px] text-slate-700 break-words"
          title={placeLabel(order)}
        >
          {placeLabel(order)}
        </div>
      </div>

      <div className="flex items-center gap-2 pt-0.5">
        <button
          type="button"
          className={
            order.status === "DONE" && order.isPaid
              ? "flex-1 rounded-xl px-2 py-1.5 text-[11px] font-medium text-slate-500 text-left"
              : "flex-1 rounded-xl px-2 py-1.5 text-[11px] font-medium bg-slate-900 text-white"
          }
          onClick={async (e) => {
            e.stopPropagation();
            if (order.status === "DONE") {
              if (order.isPaid) return;
              try {
                const u = await patchOrderPaid(order.id, true);
                onPaidUpdated(u);
              } catch {
                alert("Не удалось обновить оплату");
              }
              return;
            }
            if (nextStatus) {
              onChangeStatus(nextStatus);
            }
          }}
          disabled={(order.status !== "DONE" && !nextStatus) || isUpdating}
        >
          {primaryActionLabel(order)}
        </button>

        {printable && (
          <button
            type="button"
            className="shrink-0 rounded-xl px-2.5 py-1.5 text-[11px] font-medium border border-slate-200 bg-slate-50 text-slate-700"
            onClick={(e) => {
              e.stopPropagation();
              void onPrint(order);
            }}
            disabled={isPrinting}
            title="Печать"
            aria-label="Печать заказа"
          >
            <PrinterIcon />
          </button>
        )}
        <div className="relative" ref={pickerRef}>
          <button
            type="button"
            className="rounded-xl px-2 py-1.5 text-[11px] font-medium border border-slate-200 bg-slate-50"
            onClick={(e) => {
              e.stopPropagation();
              setStatusPickerOpen((prev) => !prev);
            }}
            disabled={isUpdating}
          >
            ⇅
          </button>
          {statusPickerOpen && (
            <div className="absolute right-0 mt-1 w-36 bg-white rounded-2xl shadow-lg border border-slate-100 z-20">
              {STATUS_PICKER_OPTIONS.map(
                (s) => (
                  <button
                    key={s}
                    type="button"
                    className={
                      "w-full text-left px-3 py-1.5 text-[10px] hover:bg-slate-50 " +
                      (order.status === s
                        ? "font-semibold text-slate-900"
                        : "text-slate-700")
                    }
                    onClick={(e) => {
                      e.stopPropagation();
                      setStatusPickerOpen(false);
                      if (s !== order.status) {
                        onChangeStatus(s);
                      }
                    }}
                  >
                    {STATUS_LABEL[s]}
                  </button>
                )
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

interface OrderDetailsModalProps {
  order: AdminOrder;
  isPrinting: boolean;
  onPrint: (order: AdminOrder, items: AdminOrderItem[], userInfo: { username: string; phone: string } | null) => Promise<void> | void;
  onPaidUpdated: (order: AdminOrder) => void;
  onClose: () => void;
}

const OrderDetailsModal: React.FC<OrderDetailsModalProps> = ({
  order,
  isPrinting,
  onPrint,
  onPaidUpdated,
  onClose,
}) => {
  const [items, setItems] = useState<AdminOrderItem[]>([]);
  const [userInfo, setUserInfo] = useState<{ username: string; phone: string } | null>(null);
  const [weightInputs, setWeightInputs] = useState<Record<number, string[]>>({});
  const [isWeightSaving, setIsWeightSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [isPaidUpdating, setIsPaidUpdating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [positions, user] = await Promise.all([
          fetchOrderPositions(order.id),
          fetchUser(order.userId),
        ]);
        if (!cancelled) {
          setItems(positions);
          setWeightInputs(
            Object.fromEntries(
              positions.map((position) => {
                const existingWeights = position.final_weight_grams_list.length > 0
                  ? position.final_weight_grams_list
                  : position.final_weight_grams
                    ? [position.final_weight_grams]
                    : [];
                return [
                  position.id,
                  Array.from({ length: position.quantity }, (_, index) =>
                    existingWeights[index] ? String(existingWeights[index] / 1000) : ""
                  ),
                ];
              })
            )
          );
          setUserInfo(user);
        }
      } catch {
        if (!cancelled) setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [order.id, order.userId]);

  const printable = canPrintOrder(order.status);
  const weightedItems = items.filter((item) => item.requires_final_weight);
  const hasWeightedItems = weightedItems.length > 0;
  const footerColumnCount = [hasWeightedItems, printable, true].filter(Boolean).length;

  const handleWeightInputChange = (positionId: number, unitIndex: number, value: string) => {
    setWeightInputs((prev) => {
      const current = prev[positionId] ? [...prev[positionId]] : [];
      current[unitIndex] = value;
      return { ...prev, [positionId]: current };
    });
  };

  const handleSaveWeights = async () => {
    const payload: { positionId: number; finalWeightGramsList: number[] }[] = [];
    for (const item of weightedItems) {
      const values = weightInputs[item.id] ?? [];
      if (values.length < item.quantity) {
        alert("Заполните вес для каждой штуки");
        return;
      }
      const gramsList = values.slice(0, item.quantity).map((value) => {
        const raw = value.trim().replace(",", ".");
        const kg = raw ? Number(raw) : NaN;
        return Number.isFinite(kg) && kg > 0 ? Math.round(kg * 1000) : NaN;
      });
      if (gramsList.some((grams) => !Number.isFinite(grams) || grams <= 0)) {
        alert("Введите вес в кг для каждой штуки, например 7.4");
        return;
      }
      payload.push({ positionId: item.id, finalWeightGramsList: gramsList });
    }
    try {
      setIsWeightSaving(true);
      const updated = await patchOrderFinalWeights(order.id, payload);
      const positions = await fetchOrderPositions(order.id);
      setItems(positions);
      setWeightInputs(
        Object.fromEntries(
          positions.map((position) => [
            position.id,
            Array.from({ length: position.quantity }, (_, index) =>
              position.final_weight_grams_list[index]
                ? String(position.final_weight_grams_list[index] / 1000)
                : ""
            ),
          ])
        )
      );
      onPaidUpdated(updated);
    } catch {
      alert("Не удалось сохранить вес");
    } finally {
      setIsWeightSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center px-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-3xl p-4 w-full max-w-xl shadow-lg space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="text-xs text-slate-500">Заказ</div>
            <div className="text-sm font-bold text-slate-900">№{order.id}</div>
          </div>
          <button
            type="button"
            className="text-slate-400 hover:text-slate-700 text-lg leading-none"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={statusPillClass(order.status)}>
              <span className="w-1.5 h-1.5 rounded-full bg-current" />
              {statusLabel(order.status)}
            </span>
            <span
              className={
                "inline-flex items-center rounded-full border px-2 py-1 text-[10px] font-semibold " +
                paidBadgeClass(Boolean(order.isPaid))
              }
            >
              {order.isPaid ? "Оплачен" : "Не оплачен"}
            </span>
          </div>
          <span className="text-[11px] text-slate-500">
            {formatDateTime(order.createdAt)}
          </span>
        </div>

        <div className="bg-slate-50 rounded-2xl p-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[11px] text-slate-500">Итог</div>
            <div className="text-base font-bold text-slate-900">
              {Math.round(order.total)} ₽
            </div>
          </div>
          <div className="text-[11px] text-slate-600 break-words">
            {placeLabel(order)}
          </div>
        </div>

        <div className="space-y-1">
          <div className="text-[11px] font-semibold text-slate-700">Клиент</div>
          {loading ? (
            <div className="text-[11px] text-slate-500">Загрузка...</div>
          ) : (
            <>
              <div className="text-[11px] text-slate-600">
                {userInfo?.username ? `@${userInfo.username}` : "Без username"}
              </div>
              <div className="text-[11px] text-slate-600">{userInfo?.phone ?? "—"}</div>
            </>
          )}
        </div>

        <div className="space-y-1">
          <div className="text-[11px] font-semibold text-slate-700">
            Позиции
          </div>
          <div className="space-y-1 max-h-40 overflow-auto pr-1">
            {loading ? (
              <div className="text-[11px] text-slate-500">Загрузка...</div>
            ) : (
              items.map((item) => (
                <div
                  key={`${item.id}-${item.quantity}`}
                  className="rounded-xl border border-slate-100 px-2 py-2 text-xs text-slate-700"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate">{item.name}</span>
                    <span className="ml-2 text-slate-500">
                      ×{item.quantity}{item.final_weight_grams ? ` (${item.final_weight_grams / 1000} кг)` : item.weight ? ` (${item.weight} г)` : ""}
                    </span>
                  </div>
                  {item.requires_final_weight ? (
                    <div className="mt-2 space-y-1.5">
                      {Array.from({ length: item.quantity }, (_, unitIndex) => (
                        <label
                          key={`${item.id}-${unitIndex}`}
                          className="grid grid-cols-[auto_1fr] items-center gap-2 text-[11px] text-slate-500"
                        >
                          <span className="whitespace-nowrap">#{unitIndex + 1}</span>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            inputMode="decimal"
                            placeholder="Вес, кг"
                            className="w-full rounded-xl border border-slate-200 px-2 py-1.5 text-[11px]"
                            value={weightInputs[item.id]?.[unitIndex] ?? ""}
                            onChange={(e) =>
                              handleWeightInputChange(item.id, unitIndex, e.target.value)
                            }
                          />
                        </label>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </div>

        {order.comment ? (
          <div className="space-y-1">
            <div className="text-[11px] font-semibold text-slate-700">Комментарий</div>
            <div className="text-[11px] text-slate-600 break-words">{order.comment}</div>
          </div>
        ) : null}

        <div className="grid gap-2 pt-1" style={{ gridTemplateColumns: `repeat(${footerColumnCount}, minmax(0, 1fr))` }}>
          {hasWeightedItems ? (
            <button
              type="button"
              className="rounded-2xl px-3 py-2.5 text-sm font-medium border border-slate-200 bg-white text-slate-900 disabled:opacity-60"
              onClick={handleSaveWeights}
              disabled={loading || isWeightSaving}
            >
              Сохранить вес
            </button>
          ) : null}

          {printable ? (
            <button
              type="button"
              className="rounded-2xl px-3 py-2.5 text-sm font-medium border border-slate-200 bg-slate-900 text-white disabled:opacity-60"
              onClick={() => void onPrint(order, items, userInfo)}
              disabled={loading || isPrinting}
            >
              <span className="inline-flex items-center justify-center gap-2">
                <PrinterIcon className="w-4 h-4" />
                Печать
              </span>
            </button>
          ) : null}

          {order.isPaid ? (
            <div className="rounded-2xl px-3 py-2.5 text-sm font-medium border border-emerald-200 bg-emerald-50 text-emerald-900 text-center">
              Заказ оплачен
            </div>
          ) : (
            <button
              type="button"
              className="rounded-2xl px-3 py-2.5 text-sm font-medium border border-emerald-200 bg-emerald-50 text-emerald-900 disabled:opacity-60"
              onClick={async () => {
                try {
                  setIsPaidUpdating(true);
                  const updated = await patchOrderPaid(order.id, true);
                  onPaidUpdated(updated);
                } catch {
                  alert("Не удалось обновить оплату");
                } finally {
                  setIsPaidUpdating(false);
                }
              }}
              disabled={isPaidUpdating}
            >
              Оплачен
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export const AdminOrdersTab: React.FC<AdminOrdersTabProps> = ({
  restaurantId,
  restaurantName,
  hideTitle = false,
}) => {
  const [activeFilter, setActiveFilter] =
    useState<AdminOrderFilterStatus>("ALL");
  const [orders, setOrders] = useState<AdminOrder[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [printingId, setPrintingId] = useState<number | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<AdminOrder | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  const applyUpdatedOrder = (updated: AdminOrder) => {
    setOrders((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
    setSelectedOrder((prev) => (prev && prev.id === updated.id ? updated : prev));
  };

  const handlePrintOrder = async (
    order: AdminOrder,
    preloadedItems?: AdminOrderItem[],
    preloadedUser?: { username: string; phone: string } | null
  ) => {
    try {
      setPrintingId(order.id);
      const [items, userInfo] =
        preloadedItems && preloadedItems.length > 0
          ? [preloadedItems, preloadedUser ?? null]
          : await Promise.all([fetchOrderPositions(order.id), fetchUser(order.userId)]);

      await printKitchenTicket({
        restaurantName,
        orderId: order.id,
        createdAt: order.createdAt,
        statusLabel: statusLabel(order.status),
        total: order.total,
        isPaid: Boolean(order.isPaid),
        orderType: order.orderType,
        deliveryAddress: order.deliveryAddress,
        tableNumber: order.tableNumber,
        comment: order.comment,
        items,
        customerUsername: userInfo?.username ?? null,
        customerPhone: userInfo?.phone ?? null,
      });
    } catch (err) {
      console.error(err);
      alert("Не удалось открыть печать заказа");
    } finally {
      setPrintingId(null);
    }
  };

  useEffect(() => {
    if (!restaurantId || Number.isNaN(restaurantId)) return;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchAdminOrders(restaurantId, activeFilter, { todayOnly: true });
        setOrders(data);
        setSelectedOrder((prev) =>
          prev ? data.find((order) => order.id === prev.id) ?? prev : prev
        );
      } catch (err) {
        console.error(err);
        setError("Не удалось загрузить заказы. Попробуйте позже.");
      } finally {
        setLoading(false);
      }
    };

    load();
    const id = window.setInterval(load, 12000);
    return () => window.clearInterval(id);
  }, [restaurantId, activeFilter]);

  const handleOpenDetails = (order: AdminOrder) => {
    setSelectedOrder(order);
    setIsDetailsOpen(true);
  };

  const handleCloseDetails = () => {
    setIsDetailsOpen(false);
    setSelectedOrder(null);
  };

  const filters: { key: AdminOrderFilterStatus; label: string }[] = [
    { key: "ALL", label: "Все" },
    { key: "CREATED", label: "Принят" },
    { key: "ACCEPTED", label: "Собран" },
    { key: "DONE", label: "Завершён" },
    { key: "CANCELLED", label: "Отменён" },
  ];

  return (
    <div
      className={
        hideTitle
          ? "space-y-3"
          : "bg-white rounded-3xl p-3 md:p-4 shadow-sm border border-slate-100 space-y-3"
      }
    >
      {!hideTitle && (
        <div className="text-sm font-semibold text-slate-900">Управление заказами</div>
      )}

      <div className="flex gap-1 overflow-x-auto no-scrollbar pb-1">
        {filters.map((f) => {
          const isActive = activeFilter === f.key;
          return (
            <button
              key={f.key}
              type="button"
              onClick={() => setActiveFilter(f.key)}
              className={
                "px-3 py-1.5 rounded-full text-[11px] font-medium border transition-colors whitespace-nowrap " +
                (isActive
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-slate-50 text-slate-700 border-slate-200")
              }
            >
              {f.label}
            </button>
          );
        })}
      </div>

      {loading && (
        <div className="text-xs text-slate-500">Загрузка заказов...</div>
      )}

      {error && !loading && (
        <div className="text-xs text-red-500">{error}</div>
      )}

      {!loading && !error && orders.length === 0 && (
        <div className="text-xs text-slate-500">
          Пока нет заказов по текущему фильтру.
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 min-[520px]:justify-start min-[520px]:[grid-template-columns:repeat(auto-fit,10.5rem)]">
        {orders.map((order) => (
          <OrderCard
            key={order.id}
            order={order}
            isUpdating={updatingId === order.id}
            isPrinting={printingId === order.id}
            onPaidUpdated={(updated) => {
              applyUpdatedOrder(updated);
            }}
            onChangeStatus={async (newStatus) => {
              try {
                setUpdatingId(order.id);
                const updated = await updateAdminOrderStatus(
                  order.id,
                  newStatus,
                  order
                );
                applyUpdatedOrder(updated);
              } catch (err) {
                console.error(err);
                alert("Не удалось обновить статус заказа");
              } finally {
                setUpdatingId(null);
              }
            }}
            onOpenDetails={handleOpenDetails}
            onPrint={handlePrintOrder}
          />
        ))}
      </div>

      {isDetailsOpen && selectedOrder && (
        <OrderDetailsModal
          order={selectedOrder}
          isPrinting={printingId === selectedOrder.id}
          onPrint={(order, items, userInfo) => handlePrintOrder(order, items, userInfo)}
          onPaidUpdated={applyUpdatedOrder}
          onClose={handleCloseDetails}
        />
      )}
    </div>
  );
};
