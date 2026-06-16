import type { AdminOrder } from "./adminOrder";

export type AnalyticsPeriod = "today" | "7d" | "30d";

export interface AdminAnalyticsSummary {
  period: AnalyticsPeriod;
  from_date: string;
  to_date: string;
  orders_count: number;
  revenue: number;
  avg_check: number;
  delivery_orders: number;
  dine_in_orders: number;
  paid_orders_count: number;
  unpaid_orders_count: number;
  paid_revenue: number;
  unpaid_revenue: number;
  previous_revenue?: number;
  revenue_delta_percent?: number | null;
}

export interface AdminAnalyticsDailyPoint {
  date: string;
  orders_count: number;
  revenue: number;
}

export interface AdminAnalyticsDailySeries {
  period: AnalyticsPeriod;
  from_date: string;
  to_date: string;
  points: AdminAnalyticsDailyPoint[];
}

export interface AdminAnalyticsDayReport {
  date: string;
  orders_count: number;
  revenue: number;
  avg_check: number;
  delivery_orders: number;
  dine_in_orders: number;
  paid_orders_count: number;
  unpaid_orders_count: number;
  unpaid_total: number;
  orders: AdminOrder[];
}
