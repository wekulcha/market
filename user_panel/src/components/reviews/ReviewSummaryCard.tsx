import type { CustomerReviewSummary } from '../../types/review';
import { formatAverageRating, formatReviewsCount, reviewStars } from '../../utils/reviews';

interface ReviewSummaryCardProps {
  summary: CustomerReviewSummary | undefined;
  loading?: boolean;
  onClick: () => void;
}

export function ReviewSummaryCard({ summary, loading = false, onClick }: ReviewSummaryCardProps) {
  const count = summary?.reviews_count ?? 0;
  const latestReview = summary?.reviews.find((review) => review.text?.trim());
  const hasReviews = count > 0;

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full overflow-hidden rounded-2xl border border-emerald-100 bg-white text-left shadow-sm transition-transform active:scale-[0.99]"
    >
      <div className="bg-emerald-50 px-3 py-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">
              Отзывы клиентов
            </div>
            <div className="mt-1 flex items-end gap-2">
              <span className="text-2xl font-bold leading-none text-slate-950">
                {loading ? '—' : formatAverageRating(summary?.average_rating ?? null)}
              </span>
              <span className="pb-0.5 text-xs font-medium text-amber-500">
                {reviewStars(summary?.average_rating ?? 0)}
              </span>
            </div>
          </div>
          <span className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm">
            Смотреть ›
          </span>
        </div>
        <div className="mt-2 text-xs text-slate-600">
          {loading ? 'Загружаем отзывы…' : hasReviews ? formatReviewsCount(count) : 'Отзывов пока нет'}
        </div>
      </div>
      {latestReview && (
        <div className="px-3 py-3">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="font-semibold text-slate-800">{latestReview.display_name}</span>
            <span>{latestReview.masked_phone}</span>
          </div>
          <p className="mt-1 line-clamp-2 text-sm leading-snug text-slate-700">
            {latestReview.text}
          </p>
        </div>
      )}
    </button>
  );
}
