import {
  AnalyticsPeriod,
  AdminAnalyticsSummary,
  AdminAnalyticsDailySeries,
} from "../types/adminAnalytics";
import { fetchAdminOrders } from "./adminOrders";

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

export async function fetchAnalyticsSummary(
  restaurantId: number,
  period: AnalyticsPeriod
): Promise<AdminAnalyticsSummary> {
  const orders = await fetchAdminOrders(restaurantId, "ALL");
  const { from, to } = getPeriodRange(period);
  const filtered = orders.filter((o) => {
    const created = new Date(o.createdAt).getTime();
    return created >= from.getTime() && created <= to.getTime();
  });
  const revenue = filtered.reduce((sum, o) => sum + Number(o.total), 0);
  const orders_count = filtered.length;
  const avg_check = orders_count > 0 ? revenue / orders_count : 0;
  const delivery_orders = filtered.filter((o) => o.orderType === "DELIVERY").length;
  const dine_in_orders = filtered.filter((o) => o.orderType === "DINE_IN").length;
  const paid_orders = filtered.filter((o) => o.isPaid);
  const unpaid_orders = filtered.filter((o) => !o.isPaid);
  const paid_revenue = paid_orders.reduce((s, o) => s + Number(o.total), 0);
  const unpaid_revenue = unpaid_orders.reduce((s, o) => s + Number(o.total), 0);

  return {
    period,
    from_date: from.toISOString().slice(0, 10),
    to_date: to.toISOString().slice(0, 10),
    orders_count,
    revenue,
    avg_check,
    delivery_orders,
    dine_in_orders,
    paid_orders_count: paid_orders.length,
    unpaid_orders_count: unpaid_orders.length,
    paid_revenue,
    unpaid_revenue,
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
        pointsByDate[key].orders_count += 1;
        pointsByDate[key].revenue += Number(o.total);
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
