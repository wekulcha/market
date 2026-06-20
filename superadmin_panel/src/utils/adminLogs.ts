const HAS_TIMEZONE_RE = /(?:z|[+-]\d{2}:?\d{2})$/i;

function parseApiDate(value: string): Date {
  const normalized = HAS_TIMEZONE_RE.test(value) ? value : `${value}Z`;
  return new Date(normalized);
}

export function formatMoscowDateTime(value: string): string {
  const date = parseApiDate(value);
  if (Number.isNaN(date.getTime())) return value;

  return `${date.toLocaleString("ru-RU", {
    timeZone: "Europe/Moscow",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })} МСК`;
}

export function metadataText(metadata: Record<string, unknown> | null): string {
  if (!metadata || Object.keys(metadata).length === 0) return "";
  return JSON.stringify(metadata);
}
