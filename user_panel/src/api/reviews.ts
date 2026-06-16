import type { CustomerReview, CustomerReviewSummary } from '../types/review';
import { apiFetchJson } from './client';

interface CustomerReviewDto {
  id: number;
  maskedPhone: string;
  rating: number;
  text?: string | null;
  createdAt?: string | null;
}

interface CustomerReviewSummaryDto {
  reviewsCount: number;
  averageRating?: number | string | null;
  reviews: CustomerReviewDto[];
}

function toNumber(value: number | string | null | undefined): number | null {
  if (value == null) return null;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function toCustomerReview(dto: CustomerReviewDto): CustomerReview {
  return {
    id: dto.id,
    masked_phone: dto.maskedPhone,
    rating: dto.rating,
    text: dto.text ?? null,
    created_at: dto.createdAt ?? null,
  };
}

export async function fetchCustomerReviews(limit = 50): Promise<CustomerReviewSummary> {
  const dto = await apiFetchJson<CustomerReviewSummaryDto>(`/orders/reviews?limit=${limit}`);
  return {
    reviews_count: dto.reviewsCount,
    average_rating: toNumber(dto.averageRating),
    reviews: dto.reviews.map(toCustomerReview),
  };
}
