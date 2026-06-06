import { useQuery } from "@tanstack/react-query";
import { fetchAdminStats } from "../api/admin";

export function AnalyticsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "stats"],
    queryFn: fetchAdminStats,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Сводка</h1>
      {isLoading && <p className="text-sm text-slate-500">Загрузка…</p>}
      {error && <p className="text-sm text-red-600">{String(error)}</p>}
      {data && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="bg-white rounded-3xl p-4 shadow-sm border border-slate-100">
            <div className="text-[11px] text-slate-500 uppercase tracking-wide">Пользователи</div>
            <div className="text-2xl font-semibold text-slate-900 mt-1">{data.users}</div>
          </div>
          <div className="bg-white rounded-3xl p-4 shadow-sm border border-slate-100">
            <div className="text-[11px] text-slate-500 uppercase tracking-wide">Магазины</div>
            <div className="text-2xl font-semibold text-slate-900 mt-1">{data.restaurants}</div>
          </div>
          <div className="bg-white rounded-3xl p-4 shadow-sm border border-slate-100">
            <div className="text-[11px] text-slate-500 uppercase tracking-wide">Заказы (всего)</div>
            <div className="text-2xl font-semibold text-slate-900 mt-1">{data.orders}</div>
          </div>
        </div>
      )}
      <p className="text-xs text-slate-500">
        Детальная аналитика GMV и отчёты могут быть добавлены позже; сейчас — базовые счётчики из базы.
      </p>
    </div>
  );
}
