import { useEffect, useState } from "react";
import { fetchAdminUserActivity, fetchAdminUsers } from "../api/admin";
import { BASE_URL } from "../api/baseUrl";
import type { AdminUserActivityLog, AdminUserOverview } from "../types/admin";

function formatLogDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function metadataText(metadata: Record<string, unknown> | null): string {
  if (!metadata || Object.keys(metadata).length === 0) return "";
  return JSON.stringify(metadata);
}

export function ToolsPage() {
  const [health, setHealth] = useState<string | null>(null);
  const [healthErr, setHealthErr] = useState<string | null>(null);
  const [users, setUsers] = useState<AdminUserOverview[]>([]);
  const [usersErr, setUsersErr] = useState<string | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [logs, setLogs] = useState<AdminUserActivityLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsErr, setLogsErr] = useState<string | null>(null);

  useEffect(() => {
    const origin = (() => {
      try {
        return new URL(BASE_URL, window.location.href).origin;
      } catch {
        return "";
      }
    })();
    if (!origin) return;
    void fetch(`${origin}/health`)
      .then(async (r) => {
        const t = await r.text();
        setHealth(r.ok ? t || `OK (${r.status})` : `HTTP ${r.status}`);
      })
      .catch((e: unknown) => setHealthErr(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(() => {
    void fetchAdminUsers()
      .then((items) => {
        const sorted = [...items].sort((a, b) => {
          const au = a.username || String(a.id);
          const bu = b.username || String(b.id);
          return au.localeCompare(bu, "ru");
        });
        setUsers(sorted);
        setSelectedUserId((prev) => prev ?? sorted[0]?.id ?? null);
      })
      .catch((e: unknown) => setUsersErr(e instanceof Error ? e.message : String(e)));
  }, []);

  const loadLogs = (userId: number | null = selectedUserId) => {
    if (!userId) return;
    setLogsLoading(true);
    setLogsErr(null);
    void fetchAdminUserActivity(userId)
      .then(setLogs)
      .catch((e: unknown) => setLogsErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setLogsLoading(false));
  };

  useEffect(() => {
    if (!selectedUserId) return;
    loadLogs(selectedUserId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedUserId]);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Инструменты</h1>
      <div className="bg-white rounded-3xl p-4 shadow-sm border border-slate-100 space-y-3 text-sm text-slate-700">
        <div>
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Backend /health</div>
          {healthErr && <p className="text-xs text-red-600">{healthErr}</p>}
          {!healthErr && health && (
            <pre className="text-xs bg-slate-50 rounded-xl p-2 overflow-x-auto whitespace-pre-wrap">{health}</pre>
          )}
          {!healthErr && !health && <p className="text-xs text-slate-500">Проверка…</p>}
        </div>
        <div className="text-xs text-slate-500 border-t border-slate-100 pt-3">
          <p className="font-medium text-slate-700 mb-1">Напоминание по секретам</p>
          <ul className="list-disc pl-4 space-y-1">
            <li>
              <code className="text-[11px] bg-slate-100 px-1 rounded">MARKET_INTERNAL_API_SECRET</code> — одинаковый в
              backend и admin_bot (кнопки статуса заказа в Telegram).
            </li>
            <li>
              <code className="text-[11px] bg-slate-100 px-1 rounded">MARKET_BOT_API_SECRET</code> — backend и user_bot.
            </li>
          </ul>
        </div>
      </div>

      <div className="bg-white rounded-3xl p-4 shadow-sm border border-slate-100 space-y-3 text-sm text-slate-700">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Логи пользователей</div>
            <p className="text-xs text-slate-500 mt-1">Последние действия выбранного пользователя в mini app и боте.</p>
          </div>
          <button
            type="button"
            onClick={() => loadLogs()}
            disabled={!selectedUserId || logsLoading}
            className="rounded-xl bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:bg-slate-300"
          >
            Обновить
          </button>
        </div>

        {usersErr && <p className="text-xs text-red-600">{usersErr}</p>}
        <select
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
          value={selectedUserId ?? ""}
          onChange={(event) => setSelectedUserId(Number(event.target.value) || null)}
        >
          {users.map((user) => (
            <option key={user.id} value={user.id}>
              {user.username ? `@${user.username.replace(/^@/, "")}` : "без username"} · {user.id} · {user.phone || "без телефона"}
            </option>
          ))}
        </select>

        {logsErr && <p className="text-xs text-red-600">{logsErr}</p>}
        {logsLoading && <p className="text-xs text-slate-500">Загружаем логи…</p>}
        {!logsLoading && logs.length === 0 && (
          <p className="rounded-xl bg-slate-50 px-3 py-3 text-xs text-slate-500">Пока нет событий по этому пользователю.</p>
        )}
        {!logsLoading && logs.length > 0 && (
          <div className="overflow-hidden rounded-2xl border border-slate-100">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-3 py-2 font-semibold">Время</th>
                  <th className="px-3 py-2 font-semibold">Источник</th>
                  <th className="px-3 py-2 font-semibold">Событие</th>
                  <th className="px-3 py-2 font-semibold">Данные</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td className="px-3 py-2 whitespace-nowrap text-slate-500">{formatLogDate(log.createdAt)}</td>
                    <td className="px-3 py-2 whitespace-nowrap">{log.source}</td>
                    <td className="px-3 py-2 font-medium text-slate-800">{log.event}</td>
                    <td className="px-3 py-2 font-mono text-[11px] text-slate-500 break-all">
                      {metadataText(log.metadata)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
