import type { CustomerReview } from '../../types/review';
import { formatReviewDate, reviewStars } from '../../utils/reviews';

interface ReviewCardProps {
  review: CustomerReview;
}

function reviewerInitial(name: string): string {
  const cleaned = name.trim();
  return cleaned ? cleaned[0].toUpperCase() : 'К';
}

export function ReviewCard({ review }: ReviewCardProps) {
  const date = formatReviewDate(review.created_at);

  return (
    <article className="rounded-2xl border border-slate-100 bg-white p-3 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-emerald-50 text-sm font-bold text-emerald-700">
          {reviewerInitial(review.display_name)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-slate-950">
                {review.display_name}
              </div>
              <div className="text-xs text-slate-500">{review.masked_phone}</div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-xs font-semibold text-amber-500">{reviewStars(review.rating)}</div>
              <div className="text-[11px] text-slate-400">
                {date || `Оценка ${review.rating}`}
              </div>
            </div>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-slate-700">
            {review.text?.trim() || 'Покупатель оставил оценку без текста.'}
          </p>
        </div>
      </div>
    </article>
  );
}
