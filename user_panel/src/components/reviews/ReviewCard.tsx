import type { CustomerReview } from '../../types/review';
import { formatReviewDate, reviewStars } from '../../utils/reviews';

interface ReviewCardProps {
  review: CustomerReview;
}

export function ReviewCard({ review }: ReviewCardProps) {
  const date = formatReviewDate(review.created_at);
  const text = review.text?.trim();

  return (
    <article className="rounded-xl border border-slate-100 bg-white p-2.5 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-950">
            {review.masked_phone}
          </div>
          <div className="text-[11px] text-slate-400">
            {date || `Оценка ${review.rating}`}
          </div>
        </div>
        <div className="shrink-0 text-right text-[11px] font-semibold text-amber-500">
          {reviewStars(review.rating)}
        </div>
      </div>
      {text && (
        <p className="mt-2 text-[13px] leading-snug text-slate-700">
          {text}
        </p>
      )}
    </article>
  );
}
