import type { AdminOrderItem } from "../types/adminOrder";
import {
  isTelegramDesktopLike,
  openTelegramExternalLink,
} from "../telegram/initTelegram";

const ATOL_PAPER_WIDTH_MM = 80;
const ATOL_PAGE_MARGIN_MM = 3;
const ATOL_CONTENT_WIDTH_MM = ATOL_PAPER_WIDTH_MM - ATOL_PAGE_MARGIN_MM * 2;

interface KitchenTicketPayload {
  restaurantName?: string;
  orderId: number;
  createdAt: string;
  statusLabel: string;
  total: number;
  isPaid: boolean;
  orderType: "DELIVERY" | "DINE_IN";
  deliveryAddress?: string | null;
  tableNumber?: string | null;
  comment?: string | null;
  items: AdminOrderItem[];
  customerUsername?: string | null;
  customerPhone?: string | null;
}

interface RenderKitchenTicketOptions {
  showPrintButton?: boolean;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatPrintedDate(iso: string): string {
  const dt = new Date(iso);
  const day = dt.getDate().toString().padStart(2, "0");
  const month = (dt.getMonth() + 1).toString().padStart(2, "0");
  const year = dt.getFullYear();
  const hh = dt.getHours().toString().padStart(2, "0");
  const mm = dt.getMinutes().toString().padStart(2, "0");
  return `${day}.${month}.${year} ${hh}:${mm}`;
}

function formatItemQuantity(item: AdminOrderItem): string {
  const finalWeight = item.final_weight_grams_list.length > 0
    ? item.final_weight_grams_list.reduce((sum, grams) => sum + grams, 0)
    : item.final_weight_grams;
  if (finalWeight) {
    return `×${item.quantity} (${finalWeight / 1000} кг)`;
  }
  return `×${item.quantity}${item.weight ? ` (${item.weight} г)` : ""}`;
}

function toBase64Url(value: string): string {
  const encoded = btoa(unescape(encodeURIComponent(value)));
  return encoded.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function fromBase64Url(value: string): string {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return decodeURIComponent(escape(atob(padded)));
}

export function encodeKitchenTicketPayload(payload: KitchenTicketPayload): string {
  return toBase64Url(JSON.stringify(payload));
}

export function decodeKitchenTicketPayload(search: string): KitchenTicketPayload {
  const params = new URLSearchParams(search);
  const raw = params.get("payload");
  if (!raw) {
    throw new Error("В ссылке печати отсутствуют данные заказа.");
  }
  return JSON.parse(fromBase64Url(raw)) as KitchenTicketPayload;
}

export function buildKitchenTicketPrintUrl(payload: KitchenTicketPayload): string {
  const url = new URL("/print-ticket", window.location.origin);
  url.searchParams.set("payload", encodeKitchenTicketPayload(payload));
  url.searchParams.set("autoprint", "1");
  return url.toString();
}

export function renderKitchenTicketDocument(
  payload: KitchenTicketPayload,
  options: RenderKitchenTicketOptions = {}
): string {
  const orderTypeLabel = payload.orderType === "DINE_IN" ? "На месте" : "Доставка";
  const placeLabel =
    payload.orderType === "DINE_IN"
      ? payload.tableNumber
        ? `Место ${payload.tableNumber}`
        : "На месте"
      : payload.deliveryAddress || "Без адреса";

  const itemsMarkup =
    payload.items.length > 0
      ? payload.items
          .map(
            (item) => `
              <div class="item-row">
                <div class="item-name">${escapeHtml(item.name)}</div>
                <div class="item-qty">${escapeHtml(formatItemQuantity(item))}</div>
              </div>
            `
          )
          .join("")
      : `<div class="empty">Позиции не загружены</div>`;

  const commentMarkup = payload.comment?.trim()
    ? `
        <div class="section">
          <div class="label">Комментарий</div>
          <div class="value comment">${escapeHtml(payload.comment)}</div>
        </div>
      `
    : "";

  const customerParts = [
    payload.customerUsername ? `@${payload.customerUsername}` : "",
    payload.customerPhone ?? "",
  ].filter(Boolean);

  const customerMarkup = customerParts.length
    ? `
        <div class="section">
          <div class="label">Клиент</div>
          <div class="value">${escapeHtml(customerParts.join(" · "))}</div>
        </div>
      `
    : "";

  const controlsMarkup = options.showPrintButton
    ? `
      <div class="print-controls">
        <button type="button" class="print-button" onclick="window.print()">Печать</button>
      </div>
    `
    : "";

  return `<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8" />
    <title>Заказ №${payload.orderId}</title>
    <style>
      @page {
        size: ${ATOL_PAPER_WIDTH_MM}mm auto;
        margin: ${ATOL_PAGE_MARGIN_MM}mm;
      }

      * {
        box-sizing: border-box;
      }

      html, body {
        margin: 0;
        padding: 0;
        color: #0f172a;
        background: #ffffff;
        font-family: "Courier New", "Liberation Mono", monospace;
        font-size: 11px;
        line-height: 1.25;
      }

      body {
        padding: 0;
        width: ${ATOL_CONTENT_WIDTH_MM}mm;
      }

      .print-controls {
        width: ${ATOL_CONTENT_WIDTH_MM}mm;
        margin: 0 auto 12px;
        display: flex;
        justify-content: center;
      }

      .print-button {
        appearance: none;
        border: 1px solid #cbd5e1;
        border-radius: 999px;
        background: #0f172a;
        color: #ffffff;
        cursor: pointer;
        font: inherit;
        font-size: 12px;
        font-weight: 700;
        padding: 8px 16px;
      }

      .ticket {
        width: ${ATOL_CONTENT_WIDTH_MM}mm;
        margin: 0 auto;
      }

      .header {
        border-bottom: 1px dashed #94a3b8;
        padding-bottom: 6px;
        margin-bottom: 8px;
      }

      .restaurant {
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
      }

      .order-number {
        margin-top: 3px;
        font-size: 20px;
        font-weight: 800;
      }

      .meta {
        margin-top: 5px;
        display: grid;
        gap: 2px;
      }

      .meta-line {
        display: flex;
        justify-content: space-between;
        gap: 6px;
      }

      .label {
        color: #475569;
        font-size: 9px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 3px;
      }

      .section {
        margin-bottom: 8px;
      }

      .value {
        font-size: 11px;
        word-break: break-word;
      }

      .place-block {
        margin-bottom: 10px;
      }

      .place-value {
        font-size: 18px;
        line-height: 1.15;
        font-weight: 800;
        word-break: break-word;
      }

      .place-note {
        margin-top: 4px;
        font-size: 10px;
        color: #64748b;
      }

      .comment {
        font-size: 13px;
        font-weight: 700;
      }

      .items {
        border-top: 1px dashed #94a3b8;
        border-bottom: 1px dashed #94a3b8;
        padding: 6px 0;
        margin-bottom: 8px;
      }

      .item-row {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 6px;
        padding: 3px 0;
      }

      .item-name {
        font-size: 15px;
        font-weight: 700;
        flex: 1;
      }

      .item-qty {
        font-size: 17px;
        font-weight: 800;
        white-space: nowrap;
      }

      .summary {
        display: grid;
        gap: 3px;
      }

      .total {
        font-size: 15px;
        font-weight: 800;
      }

      .empty {
        color: #64748b;
      }

      @media print {
        html, body {
          width: ${ATOL_CONTENT_WIDTH_MM}mm;
        }

        .print-controls {
          display: none;
        }

        .ticket {
          width: ${ATOL_CONTENT_WIDTH_MM}mm;
        }
      }
    </style>
  </head>
  <body>
    ${controlsMarkup}
    <div class="ticket">
      <div class="header">
        <div class="restaurant">${escapeHtml(payload.restaurantName || "Kulcha Market")}</div>
        <div class="order-number">Заказ №${payload.orderId}</div>
        <div class="meta">
          <div class="meta-line"><span>${escapeHtml(formatPrintedDate(payload.createdAt))}</span><span>${escapeHtml(payload.statusLabel)}</span></div>
        </div>
      </div>

      <div class="place-block">
        <div class="label">Куда отдать</div>
        <div class="place-value">${escapeHtml(placeLabel)}</div>
        <div class="place-note">${escapeHtml(orderTypeLabel)}</div>
      </div>

      ${customerMarkup}

      <div class="section">
        <div class="items">${itemsMarkup}</div>
      </div>

      ${commentMarkup}

      <div class="summary">
        <div class="label">Итог</div>
        <div class="total">${Math.round(payload.total)} ₽</div>
      </div>
    </div>
  </body>
</html>`;
}

function printWithPopup(html: string, title: string): void {
  const printWindow = window.open("", "_blank", "noopener,noreferrer,width=480,height=720");
  if (!printWindow) {
    throw new Error("Браузер заблокировал окно печати.");
  }
  printWindow.document.open();
  printWindow.document.write(html);
  printWindow.document.close();
  printWindow.document.title = title;
  printWindow.focus();
  window.setTimeout(() => {
    printWindow.print();
  }, 250);
}

export async function printKitchenTicket(payload: KitchenTicketPayload): Promise<void> {
  if (isTelegramDesktopLike()) {
    const externalUrl = buildKitchenTicketPrintUrl(payload);
    const opened = openTelegramExternalLink(externalUrl);
    if (!opened) {
      throw new Error("Не удалось открыть страницу печати во внешнем браузере.");
    }
    return;
  }

  const html = renderKitchenTicketDocument(payload);
  const title = `Заказ №${payload.orderId}`;

  const iframe = document.createElement("iframe");
  iframe.setAttribute("aria-hidden", "true");
  iframe.style.position = "fixed";
  iframe.style.right = "0";
  iframe.style.bottom = "0";
  iframe.style.width = "0";
  iframe.style.height = "0";
  iframe.style.border = "0";
  iframe.style.opacity = "0";

  document.body.appendChild(iframe);

  try {
    const frameDoc = iframe.contentDocument;
    const frameWindow = iframe.contentWindow;

    if (!frameDoc || !frameWindow) {
      throw new Error("Не удалось подготовить скрытый документ для печати.");
    }

    frameDoc.open();
    frameDoc.write(html);
    frameDoc.close();
    frameDoc.title = title;

    await new Promise<void>((resolve) => {
      window.setTimeout(resolve, 150);
    });

    frameWindow.focus();
    frameWindow.print();

    const cleanup = () => {
      iframe.remove();
      window.removeEventListener("afterprint", cleanup);
    };

    window.addEventListener("afterprint", cleanup, { once: true });
    window.setTimeout(cleanup, 1500);
  } catch {
    iframe.remove();
    printWithPopup(html, title);
  }
}
