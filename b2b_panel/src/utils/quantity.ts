const EPSILON = 1e-8;

function decimals(value: number): number {
  const text = String(value);
  const index = text.indexOf('.');
  return index === -1 ? 0 : text.length - index - 1;
}

function roundLike(value: number, reference: number): number {
  const precision = Math.min(6, Math.max(decimals(reference), 0));
  return Number(value.toFixed(precision));
}

export function normalizeQuantity(value: number, minimum: number, step: number): number {
  if (!Number.isFinite(value) || !Number.isFinite(minimum) || !Number.isFinite(step) || minimum <= 0 || step <= 0) {
    throw new Error('Некорректные правила количества');
  }
  if (value <= minimum) return minimum;
  const increments = Math.round((value - minimum) / step);
  return roundLike(minimum + Math.max(0, increments) * step, step);
}

export function incrementQuantity(value: number, minimum: number, step: number): number {
  const current = normalizeQuantity(value, minimum, step);
  return roundLike(current + step, step);
}

export function decrementQuantity(value: number, minimum: number, step: number): number {
  const current = normalizeQuantity(value, minimum, step);
  return Math.max(minimum, roundLike(current - step, step));
}

export function isValidQuantity(value: number, minimum: number, step: number): boolean {
  if (![value, minimum, step].every(Number.isFinite) || minimum <= 0 || step <= 0 || value + EPSILON < minimum) {
    return false;
  }
  const increments = (value - minimum) / step;
  return Math.abs(increments - Math.round(increments)) < EPSILON;
}
