export function formatAverageRating(value: number | null): string {
  if (value == null) return '—';
  return value.toFixed(value % 1 === 0 ? 0 : 1);
}

export function formatReviewsCount(count: number): string {
  const abs = Math.abs(count);
  const lastTwo = abs % 100;
  const last = abs % 10;
  if (lastTwo >= 11 && lastTwo <= 14) return `${count} отзывов`;
  if (last === 1) return `${count} отзыв`;
  if (last >= 2 && last <= 4) return `${count} отзыва`;
  return `${count} отзывов`;
}

export function reviewStars(rating: number | null | undefined): string {
  const rounded = Math.max(0, Math.min(5, Math.round(rating ?? 0)));
  return `${'★'.repeat(rounded)}${'☆'.repeat(5 - rounded)}`;
}

export function formatReviewDate(value: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: 'long',
  });
}
