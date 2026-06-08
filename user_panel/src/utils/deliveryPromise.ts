import { MARKET_DEFAULT_DELIVERY_CUTOFF } from '../config/market';

function parseTimeToMinutes(value: string | null | undefined): number | null {
  if (!value) return null;
  const match = value.trim().match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (!Number.isInteger(hours) || !Number.isInteger(minutes)) return null;
  if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) return null;
  return hours * 60 + minutes;
}

function getMoscowNowMinutes(): number {
  const parts = new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Europe/Moscow',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date());
  const hours = Number(parts.find((part) => part.type === 'hour')?.value ?? '0');
  const minutes = Number(parts.find((part) => part.type === 'minute')?.value ?? '0');
  return hours * 60 + minutes;
}

export function normalizeDeliveryCutoff(value: string | null | undefined): string {
  return parseTimeToMinutes(value) == null ? MARKET_DEFAULT_DELIVERY_CUTOFF : value!.trim();
}

export function deliveryDayLabel(cutoff: string | null | undefined): 'сегодня' | 'завтра' {
  const cutoffMinutes = parseTimeToMinutes(normalizeDeliveryCutoff(cutoff));
  if (cutoffMinutes == null) return 'сегодня';
  return getMoscowNowMinutes() <= cutoffMinutes ? 'сегодня' : 'завтра';
}

export function deliveryPromiseText(cutoff: string | null | undefined): string {
  return `Доставим ${deliveryDayLabel(cutoff)}`;
}

export function deliveryCutoffHint(cutoff: string | null | undefined): string {
  const normalized = normalizeDeliveryCutoff(cutoff);
  return `Заказы до ${normalized} доставляем сегодня, после ${normalized} — завтра.`;
}
