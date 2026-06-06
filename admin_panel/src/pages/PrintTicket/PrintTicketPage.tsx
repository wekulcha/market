import React, { useEffect, useMemo, useState } from "react";
import {
  decodeKitchenTicketPayload,
  renderKitchenTicketDocument,
} from "../../utils/printKitchenTicket";

export const PrintTicketPage: React.FC = () => {
  const parsed = useMemo(() => {
    try {
      return {
        payload: decodeKitchenTicketPayload(window.location.search),
        error: null,
      };
    } catch (err) {
      return {
        payload: null,
        error: err instanceof Error ? err.message : "Не удалось открыть чек.",
      };
    }
  }, []);
  const [error] = useState<string | null>(parsed.error);
  const payload = parsed.payload;

  useEffect(() => {
    if (!payload) return;

    const html = renderKitchenTicketDocument(payload, { showPrintButton: true });
    document.open();
    document.write(html);
    document.close();

    const autoPrint = new URLSearchParams(window.location.search).get("autoprint");
    if (autoPrint === "1") {
      window.setTimeout(() => {
        window.print();
      }, 350);
    }
  }, [payload]);

  if (!payload) {
    return (
      <main className="min-h-screen bg-slate-100 flex items-center justify-center px-4">
        <div className="max-w-sm rounded-3xl border border-rose-200 bg-white p-6 text-center shadow-sm">
          <p className="text-base font-semibold text-slate-900">Чек не открыт</p>
          <p className="mt-2 text-sm text-slate-600">
            {error ?? "Не удалось прочитать данные заказа для печати."}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-100 flex items-center justify-center px-4">
      <div className="max-w-sm rounded-3xl border border-slate-200 bg-white p-6 text-center shadow-sm">
        <p className="text-base font-semibold text-slate-900">Подготавливаем чек…</p>
        <p className="mt-2 text-sm text-slate-600">
          Если диалог печати не открылся автоматически, воспользуйтесь кнопкой
          печати на странице.
        </p>
      </div>
    </main>
  );
};
