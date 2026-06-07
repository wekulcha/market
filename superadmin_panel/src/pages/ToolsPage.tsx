import { useEffect, useState } from "react";
import { BASE_URL } from "../api/baseUrl";

export function ToolsPage() {
  const [health, setHealth] = useState<string | null>(null);
  const [healthErr, setHealthErr] = useState<string | null>(null);

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
    </div>
  );
}
