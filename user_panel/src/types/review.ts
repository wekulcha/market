export interface CustomerReview {
  id: number;
  display_name: string;
  masked_phone: string;
  rating: number;
  text: string | null;
  created_at: string | null;
}

export interface CustomerReviewSummary {
  reviews_count: number;
  average_rating: number | null;
  reviews: CustomerReview[];
}
