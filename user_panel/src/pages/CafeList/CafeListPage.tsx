import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { MARKET_BRAND_NAME, MARKET_MIN_ORDER_TOTAL } from '../../config/market';
import { useAppContext } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { logUserActivity } from '../../api/activity';
import { fetchMarketRestaurant } from '../../api/restaurants';
import { fetchMealsByRestaurant } from '../../api/meals';
import { fetchCustomerReviews } from '../../api/reviews';
import { ReviewSummaryCard } from '../../components/reviews/ReviewSummaryCard';
import { Header } from '../../layout/Header';
import { MiniAppShell } from '../../layout/MiniAppShell';
import { PRODUCT_CATEGORIES, type ProductCategory } from '../../utils/productCategories';
import { deliveryPromiseText } from '../../utils/deliveryPromise';

const DEFAULT_VISIBLE_CATEGORY_KEYS = [
  'VEGETABLES_HERBS',
  'FRUITS_BERRIES',
  'DRIED_FRUITS_NUTS',
  'MEAT_POULTRY',
  'BREAD_BAKERY',
  'JUICES_SODAS',
];

const DEFAULT_VISIBLE_CATEGORIES = PRODUCT_CATEGORIES.filter((category) =>
  DEFAULT_VISIBLE_CATEGORY_KEYS.includes(category.key)
);

export function CafeListPage() {
  const navigate = useNavigate();
  const { setSelectedRestaurant, setServiceType } = useAppContext();
  const { authReady, currentUser } = useAuth();
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const { data: marketRestaurant, error: queryError, refetch } = useQuery({
    queryKey: ['market-restaurant'],
    queryFn: fetchMarketRestaurant,
  });
  const {
    data: meals = [],
    error: mealsQueryError,
    refetch: refetchMeals,
    isLoading: mealsLoading,
  } = useQuery({
    queryKey: ['market-restaurant-meals', marketRestaurant?.id],
    queryFn: () => fetchMealsByRestaurant(marketRestaurant!.id),
    enabled: Boolean(marketRestaurant?.id),
  });
  const { data: reviewSummary, isLoading: reviewsLoading } = useQuery({
    queryKey: ['customer-reviews', 3],
    queryFn: () => fetchCustomerReviews(3),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    setServiceType('DELIVERY');
  }, [setServiceType]);

  useEffect(() => {
    if (marketRestaurant) {
      setSelectedRestaurant(marketRestaurant);
    }
  }, [marketRestaurant, setSelectedRestaurant]);

  useEffect(() => {
    if (!authReady || !currentUser) return;
    logUserActivity('catalog_open');
  }, [authReady, currentUser]);

  const normalizedSearch = searchQuery.toLowerCase().trim();
  const categoriesWithProducts = useMemo(() => {
    const keys = new Set(meals.filter((meal) => meal.is_available).map((meal) => meal.category).filter(Boolean));
    return PRODUCT_CATEGORIES.filter((category) => keys.has(category.key));
  }, [meals]);
  const visibleCategories = useMemo(() => {
    const isInitialCatalogLoading = !marketRestaurant || mealsLoading;
    const source = isInitialCatalogLoading ? DEFAULT_VISIBLE_CATEGORIES : categoriesWithProducts;
    if (!normalizedSearch) return source;
    return source.filter((category) => {
      const haystack = [category.label, category.shortLabel, ...category.keywords]
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalizedSearch);
    });
  }, [categoriesWithProducts, marketRestaurant, mealsLoading, normalizedSearch]);

  const combinedError = queryError ?? mealsQueryError;
  const error = combinedError
    ? combinedError instanceof Error
      ? combinedError.message
      : 'Не удалось загрузить магазин.'
    : null;
  const deliveryText = deliveryPromiseText(marketRestaurant?.ordersAcceptTo);

  return (
    <MiniAppShell>
      <div className="space-y-4 pb-24">
        <Header
          title={MARKET_BRAND_NAME}
          onBurgerClick={() => navigate('/profile')}
          onProfileClick={() => navigate('/profile')}
          onSearchClick={() => setIsSearchOpen((prev) => !prev)}
        />

        {isSearchOpen && (
          <div className="mt-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Поиск по товарам"
              className="w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-300"
            />
          </div>
        )}

        <section className="space-y-3">
          <div className="px-1">
            <h2 className="text-xl font-semibold text-slate-950">Каталог товаров</h2>
            <p className="mt-1 text-xs text-slate-500">
              Минимальный заказ от {MARKET_MIN_ORDER_TOTAL} ₽ · {deliveryText}
            </p>
          </div>

          {error && (
            <div className="rounded-2xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              {error}
              <button
                type="button"
                onClick={() => {
                  void refetch();
                  void refetchMeals();
                }}
                className="ml-2 font-semibold underline"
              >
                Повторить
              </button>
            </div>
          )}

          {visibleCategories.length === 0 ? (
            <div className="text-center text-sm text-slate-500 mt-8">
              Ничего не найдено. Попробуйте изменить запрос.
            </div>
          ) : (
            <div className="grid grid-cols-2 min-[380px]:grid-cols-3 gap-3">
              {visibleCategories.map((category) => (
                <CategoryCard
                  key={category.key}
                  category={category}
                  onClick={() => navigate(`/catalog/${category.key}`)}
                />
              ))}
            </div>
          )}
        </section>

        <ReviewSummaryCard
          summary={reviewSummary}
          loading={reviewsLoading}
          onClick={() => navigate('/reviews')}
        />
      </div>
    </MiniAppShell>
  );
}

function CategoryCard({
  category,
  onClick,
}: {
  category: ProductCategory;
  onClick: () => void;
}) {
  const style = {
    '--category-bg': category.background,
    '--category-accent': category.accent,
  } as CSSProperties;

  return (
    <button
      type="button"
      onClick={onClick}
      style={style}
      className="relative aspect-square overflow-hidden rounded-2xl bg-[var(--category-bg)] p-3 text-left shadow-sm transition-transform active:scale-[0.98]"
    >
      <span className="relative z-10 block text-[13px] font-medium leading-tight text-slate-900">
        {category.shortLabel}
      </span>
      <span className="absolute -bottom-2 -right-2 h-16 w-16 rounded-full bg-white/45" />
      <span className="absolute bottom-3 right-2 text-3xl leading-none drop-shadow-sm">
        {category.visual}
      </span>
      <span className="absolute bottom-3 left-3 h-1.5 w-8 rounded-full bg-[var(--category-accent)]/80" />
    </button>
  );
}
