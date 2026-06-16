import {
  AnalyticsPeriod,
  AdminAnalyticsSummary,
  AdminAnalyticsDailySeries,
  AdminAnalyticsDayReport,
} from "../types/adminAnalytics";
import { fetchAdminOrders } from "./adminOrders";
import type { AdminOrder } from "../types/adminOrder";

function getPeriodRange(period: AnalyticsPeriod): { from: Date; to: Date } {
  const to = new Date();
  to.setHours(23, 59, 59, 999);
  const from = new Date(to);
  if (period === "today") {
    from.setHours(0, 0, 0, 0);
    return { from, to };
  }
  if (period === "7d") {
    from.setDate(from.getDate() - 6);
    from.setHours(0, 0, 0, 0);
    return { from, to };
  }
  from.setDate(from.getDate() - 29);
  from.setHours(0, 0, 0, 0);
  return { from, to };
}

function toDateKey(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function getPreviousRange(range: { from: Date; to: Date }): { from: Date; to: Date } {
  const durationMs = range.to.getTime() - range.from.getTime() + 1;
  const to = new Date(range.from.getTime() - 1);
  const from = new Date(to.getTime() - durationMs + 1);
  return { from, to };
}

function isInRange(order: AdminOrder, range: { from: Date; to: Date }): boolean {
  const created = new Date(order.createdAt).getTime();
  return created >= range.from.getTime() && created <= range.to.getTime();
}

function isActiveOrder(order: AdminOrder): boolean {
  return order.status !== "CANCELLED";
}

function isRevenueOrder(order: AdminOrder): boolean {
  return isActiveOrder(order) && Boolean(order.isPaid);
}

function sumTotals(orders: AdminOrder[]): number {
  return orders.reduce((sum, order) => sum + Number(order.total), 0);
}

export async function fetchAnalyticsSummary(
  restaurantId: number,
  period: AnalyticsPeriod
): Promise<AdminAnalyticsSummary> {
  const orders = await fetchAdminOrders(restaurantId, "ALL");
  const range = getPeriodRange(period);
  const previousRange = getPreviousRange(range);
  const filtered = orders.filter((o) => isInRange(o, range));
  const activeOrders = filtered.filter(isActiveOrder);
  const paid_orders = filtered.filter(isRevenueOrder);
  const unpaid_orders = activeOrders.filter((o) => !o.isPaid);
  const previousRevenue = sumTotals(
    orders.filter((o) => isInRange(o, previousRange) && isRevenueOrder(o))
  );
  const revenue = sumTotals(paid_orders);
  const orders_count = activeOrders.length;
  const avg_check = paid_orders.length > 0 ? revenue / paid_orders.length : 0;
  const delivery_orders = activeOrders.filter((o) => o.orderType === "DELIVERY").length;
  const dine_in_orders = activeOrders.filter((o) => o.orderType === "DINE_IN").length;
  const paid_revenue = revenue;
  const unpaid_revenue = sumTotals(unpaid_orders);
  const revenue_delta_percent =
    previousRevenue > 0
      ? ((revenue - previousRevenue) / previousRevenue) * 100
      : revenue > 0
        ? 100
        : 0;

  return {
    period,
    from_date: range.from.toISOString().slice(0, 10),
    to_date: range.to.toISOString().slice(0, 10),
    orders_count,
    revenue,
    avg_check,
    delivery_orders,
    dine_in_orders,
    paid_orders_count: paid_orders.length,
    unpaid_orders_count: unpaid_orders.length,
    paid_revenue,
    unpaid_revenue,
    previous_revenue: previousRevenue,
    revenue_delta_percent,
  };
}

export async function fetchAnalyticsDaily(
  restaurantId: number,
  period: AnalyticsPeriod
): Promise<AdminAnalyticsDailySeries> {
  const orders = await fetchAdminOrders(restaurantId, "ALL");
  const { from, to } = getPeriodRange(period);
  const pointsByDate: Record<string, { orders_count: number; revenue: number }> = {};
  for (let d = new Date(from); d <= to; d.setDate(d.getDate() + 1)) {
    pointsByDate[toDateKey(d)] = { orders_count: 0, revenue: 0 };
  }
  for (const o of orders) {
    const created = new Date(o.createdAt).getTime();
    if (created >= from.getTime() && created <= to.getTime()) {
      const key = toDateKey(new Date(o.createdAt));
      if (pointsByDate[key]) {
        if (isActiveOrder(o)) {
          pointsByDate[key].orders_count += 1;
        }
        if (isRevenueOrder(o)) {
          pointsByDate[key].revenue += Number(o.total);
        }
      }
    }
  }
  const points = Object.entries(pointsByDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, data]) => ({
      date,
      orders_count: data.orders_count,
      revenue: data.revenue,
    }));

  return {
    period,
    from_date: from.toISOString().slice(0, 10),
    to_date: to.toISOString().slice(0, 10),
    points,
  };
}

export async function fetchAnalyticsDayReport(
  restaurantId: number,
  date: string
): Promise<AdminAnalyticsDayReport> {
  const orders = await fetchAdminOrders(restaurantId, "ALL");
  const dayOrders = orders.filter((order) => toDateKey(new Date(order.createdAt)) === date);
  const activeOrders = dayOrders.filter(isActiveOrder);
  const paidOrders = dayOrders.filter(isRevenueOrder);
  const unpaidOrders = activeOrders.filter((order) => !order.isPaid);
  const revenue = sumTotals(paidOrders);
  const sortedOrders = [...activeOrders].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );

  return {
    date,
    orders_count: activeOrders.length,
    revenue,
    avg_check: paidOrders.length > 0 ? revenue / paidOrders.length : 0,
    delivery_orders: activeOrders.filter((order) => order.orderType === "DELIVERY").length,
    dine_in_orders: activeOrders.filter((order) => order.orderType === "DINE_IN").length,
    paid_orders_count: paidOrders.length,
    unpaid_orders_count: unpaidOrders.length,
    unpaid_total: sumTotals(unpaidOrders),
    orders: sortedOrders,
  };
}
