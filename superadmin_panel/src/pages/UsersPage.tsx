import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { deleteAdminUser, fetchAdminUsers, setUserActive } from "../api/admin";
import { ApiError } from "../api/client";
import type { AdminUserOverview } from "../types/admin";

function formatApiFailure(err: unknown): string {
  if (err instanceof ApiError) {
    try {
      const j = JSON.parse(err.body) as { detail?: unknown };
      const d = j.detail;
      if (typeof d === "string") return d;
      if (Array.isArray(d)) {
        return d
          .map((x) => (typeof x === "object" && x && "msg" in x ? String((x as { msg: string }).msg) : String(x)))
          .join("; ");
      }
    } catch {
      /* not JSON */
    }
    if (err.body) return err.body;
    return `Ошибка ${err.status}`;
  }
  if (err instanceof Error) return err.message;
  return String(err);
}

export function UsersPage() {
  const [q, setQ] = useState("");
  const [detail, setDetail] = useState<AdminUserOverview | null>(null);
  const queryClient = useQueryClient();
  const { data: users = [], isLoading, error, isError } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: fetchAdminUsers,
    retry: 1,
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) => setUserActive(id, active),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteAdminUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      setDetail(null);
    },
  });

  const filtered = useMemo(() => {
    const n = q.trim().toLowerCase();
    if (!n) return users;
    return users.filter((u) => {
      const hay = [String(u.id), u.username ?? "", u.phone ?? "", u.email ?? ""].join(" ").toLowerCase();
      return hay.includes(n);
    });
  }, [users, q]);

  return (
    <div className="space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-900">Пользователи</h1>
        <input
          type="search"
          placeholder="Поиск по ID, username, телефону…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="w-full sm:max-w-xs rounded-xl border border-slate-200 px-3 py-1.5 text-sm"
        />
      </div>
      {isLoading && <p className="text-xs text-slate-500">Загрузка…</p>}
      {isError && (
        <p className="text-xs text-red-600 whitespace-pre-wrap break-words" role="alert">
          Не удалось загрузить список. {formatApiFailure(error)}
        </p>
      )}
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-2 py-2 font-medium">ID</th>
              <th className="px-2 py-2 font-medium">Ник</th>
              <th className="px-2 py-2 font-medium">Телефон</th>
              <th className="px-2 py-2 font-medium">Статус</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((u) => {
              const active = u.isActive !== false;
              return (
                <tr
                  key={u.id}
                  onClick={() => setDetail(u)}
                  className="border-t border-slate-100 hover:bg-slate-50/80 cursor-pointer"
                >
                  <td className="px-2 py-1.5 font-mono text-[11px]">{u.id}</td>
                  <td className="px-2 py-1.5 max-w-[120px] truncate" title={u.username ?? ""}>
                    {u.username || "—"}
                  </td>
                  <td className="px-2 py-1.5 max-w-[100px] truncate" title={u.phone ?? ""}>
                    {u.phone || "—"}
                  </td>
                  <td className="px-2 py-1.5">
                    <span className={active ? "text-emerald-700" : "text-slate-400"}>
                      {active ? "активен" : "выкл."}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!isLoading && filtered.length === 0 && (
          <div className="px-3 py-3 text-xs text-slate-500">Ничего не найдено.</div>
        )}
      </div>
      {(toggleMutation.isError || deleteMutation.isError) && (
        <p className="text-xs text-red-600" role="alert">
          {formatApiFailure(toggleMutation.error ?? deleteMutation.error)}
        </p>
      )}

      {detail && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center p-4"
          onClick={() => setDetail(null)}
        >
          <div
            className="bg-white rounded-3xl p-4 w-full max-w-md max-h-[88vh] overflow-y-auto shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start gap-2 mb-3">
              <div>
                <div className="text-sm font-semibold text-slate-900">
                  {detail.username || `Пользователь ${detail.id}`}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5 font-mono">id: {detail.id}</div>
              </div>
              <button
                type="button"
                className="text-slate-400 hover:text-slate-700 text-lg leading-none"
                onClick={() => setDetail(null)}
              >
                ×
              </button>
            </div>
            <div className="text-[11px] text-slate-600 space-y-2">
              <div>
                <span className="font-semibold">Телефон:</span> {detail.phone || "—"}
              </div>
              <div>
                <span className="font-semibold">Email:</span> {detail.email || "—"}
              </div>
              <div>
                <span className="font-semibold">Адрес:</span> {detail.address || "—"}
              </div>
              <div>
                <span className="font-semibold">Курьер:</span> {detail.courier ? "да" : "нет"}
              </div>
              <div>
                <span className="font-semibold">Магазины:</span>
                <ul className="mt-1 list-disc pl-4 max-h-20 overflow-y-auto">
                  {(detail.staffAssignments ?? []).map((s) => (
                    <li key={`${s.restaurantId}-${s.permission}`}>
                      {s.restaurantName} · {s.permission}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <span className="font-semibold">Заказов в истории:</span> {detail.orderHistory?.length ?? 0}
              </div>
            </div>
            <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-slate-100">
              <button
                type="button"
                disabled={toggleMutation.isPending || deleteMutation.isPending}
                onClick={() =>
                  toggleMutation.mutate({
                    id: detail.id,
                    active: !(detail.isActive !== false),
                  })
                }
                className="flex-1 min-w-[120px] rounded-xl bg-slate-200 px-3 py-2 text-xs font-medium text-slate-800 disabled:opacity-50"
              >
                {detail.isActive !== false ? "Отключить" : "Включить"}
              </button>
              <button
                type="button"
                disabled={toggleMutation.isPending || deleteMutation.isPending}
                onClick={() => {
                  if (!window.confirm(`Удалить пользователя ${detail.id} безвозвратно? Только если нет заказов.`))
                    return;
                  deleteMutation.mutate(detail.id);
                }}
                className="flex-1 min-w-[120px] rounded-xl bg-red-50 px-3 py-2 text-xs font-medium text-red-700 disabled:opacity-50"
              >
                Удалить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
