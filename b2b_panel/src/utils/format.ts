import type { QuantityUnit } from '../types/domain';

const money = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  maximumFractionDigits: 2,
});

const dateTime = new Intl.DateTimeFormat('ru-RU', {
  timeZone: 'Europe/Moscow',
  dateStyle: 'medium',
  timeStyle: 'short',
});

export function formatMoneyKopecks(value: number | null | undefined): string {
  return value == null || !Number.isSafeInteger(value) ? '—' : money.format(value / 100);
}

export function kopecksToRublesInput(value: number | null | undefined): string {
  if (value == null || !Number.isSafeInteger(value)) return '';
  const sign = value < 0 ? '-' : '';
  const absolute = Math.abs(value);
  const rubles = Math.floor(absolute / 100);
  const kopecks = String(absolute % 100).padStart(2, '0');
  return `${sign}${rubles}.${kopecks}`;
}

export function rublesInputToKopecks(value: string): number | null {
  const normalized = value.trim().replace(',', '.');
  const match = /^(\d+)(?:\.(\d{0,2}))?$/.exec(normalized);
  if (!match) return null;
  const rubles = Number(match[1]);
  const fractional = (match[2] ?? '').padEnd(2, '0');
  const result = rubles * 100 + Number(fractional || '0');
  return Number.isSafeInteger(result) ? result : null;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : dateTime.format(parsed);
}

export const UNIT_LABELS: Record<QuantityUnit, string> = {
  KG: 'кг',
  LITER: 'л',
  PIECE: 'шт.',
  BOX: 'кор.',
  PACKAGE: 'уп.',
};

export function quantityText(value: number, unit: QuantityUnit): string {
  return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 3 }).format(value)} ${UNIT_LABELS[unit]}`;
}
