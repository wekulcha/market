import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchCustomerReviews } from '../../api/reviews';
import { ReviewCard } from '../../components/reviews/ReviewCard';
import { Header } from '../../layout/Header';
import { MiniAppShell } from '../../layout/MiniAppShell';
import { formatAverageRating, formatReviewsCount, reviewStars } from '../../utils/reviews';

const RATING_FILTERS = [0, 5, 4, 3, 2, 1] as const;

type RatingFilter = (typeof RATING_FILTERS)[number];

export function ReviewsPage() {
  const navigate = useNavigate();
  const [ratingFilter, setRatingFilter] = useState<RatingFilter>(0);
  const {
    data: summary,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['customer-reviews', 100],
    queryFn: () => fetchCustomerReviews(100),
    staleTime: 5 * 60 * 1000,
  });

  const reviews = useMemo(() => summary?.reviews ?? [], [summary?.reviews]);
  const filteredReviews = useMemo(
    () => reviews.filter((review) => ratingFilter === 0 || review.rating === ratingFilter),
    [ratingFilter, reviews]
  );
  const ratingDistribution = useMemo(
    () =>
      [5, 4, 3, 2, 1].map((rating) => ({
        rating,
        count: reviews.filter((review) => review.rating === rating).length,
      })),
    [reviews]
  );
  const maxDistributionCount = Math.max(1, ...ratingDistribution.map((item) => item.count));

  return (
    <MiniAppShell>
      <Header
        title="Отзывы"
        showSearch={false}
        showBack
        onBackClick={() => navigate(-1)}
        onHomeClick={() => navigate('/catalog')}
      />
      <main className="mt-3 space-y-3 pb-20">
        <section className="rounded-xl border border-emerald-100 bg-white p-3 text-slate-950 shadow-sm">
          <div className="flex items-end justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold text-emerald-700">Средняя оценка</div>
              <div className="mt-1 flex items-end gap-2">
                <span className="text-3xl font-bold leading-none">
                  {isLoading ? '—' : formatAverageRating(summary?.average_rating ?? null)}
                </span>
                <span className="pb-0.5 text-xs text-amber-500">
                  {reviewStars(summary?.average_rating ?? 0)}
                </span>
              </div>
            </div>
            <div className="rounded-xl bg-emerald-50 px-2.5 py-2 text-right">
              <div className="text-lg font-bold leading-none">{summary?.reviews_count ?? 0}</div>
              <div className="mt-1 text-[11px] text-slate-500">отзывов</div>
            </div>
          </div>

          {reviews.length > 0 && (
            <div className="mt-3 space-y-1.5">
              {ratingDistribution.map((item) => (
                <div key={item.rating} className="grid grid-cols-[26px_1fr_22px] items-center gap-2 text-[11px]">
                  <span className="text-slate-500">{item.rating}★</span>
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-emerald-400"
                      style={{ width: `${(item.count / maxDistributionCount) * 100}%` }}
                    />
                  </div>
                  <span className="text-right text-slate-500">{item.count}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
          {RATING_FILTERS.map((rating) => {
            const active = ratingFilter === rating;
            return (
              <button
                key={rating}
                type="button"
                aria-pressed={active}
                onClick={() => setRatingFilter(rating)}
                className={[
                  'shrink-0 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors',
                  active
                    ? 'bg-emerald-600 text-white'
                    : 'border border-slate-200 bg-white text-slate-700',
                ].join(' ')}
              >
                {rating === 0 ? 'Все' : `${rating} ★`}
              </button>
            );
          })}
        </div>

        {isLoading && (
          <div className="space-y-2">
            {[0, 1, 2].map((item) => (
              <div key={item} className="h-20 animate-pulse rounded-xl bg-white shadow-sm" />
            ))}
          </div>
        )}

        {error && (
          <section className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-xs text-amber-800">
            Не удалось загрузить отзывы.
            <button
              type="button"
              onClick={() => void refetch()}
              className="ml-2 font-semibold underline"
            >
              Повторить
            </button>
          </section>
        )}

        {!isLoading && !error && reviews.length === 0 && (
          <section className="rounded-xl bg-white p-3 text-center text-sm text-slate-500 shadow-sm">
            Отзывов пока нет.
          </section>
        )}

        {!isLoading && !error && reviews.length > 0 && filteredReviews.length === 0 && (
          <section className="rounded-xl bg-white p-3 text-center text-sm text-slate-500 shadow-sm">
            По этой оценке отзывов нет.
          </section>
        )}

        {filteredReviews.length > 0 && (
          <section className="space-y-1.5">
            <div className="px-1 text-xs text-slate-500">
              {ratingFilter === 0
                ? formatReviewsCount(summary?.reviews_count ?? filteredReviews.length)
                : formatReviewsCount(filteredReviews.length)}
            </div>
            {filteredReviews.map((review) => (
              <ReviewCard key={review.id} review={review} />
            ))}
          </section>
        )}
      </main>
    </MiniAppShell>
  );
}
