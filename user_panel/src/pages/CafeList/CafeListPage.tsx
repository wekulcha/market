import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { MARKET_BRAND_NAME, MARKET_MIN_ORDER_TOTAL } from '../../config/market';
import { useAppContext } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { logUserActivity } from '../../api/activity';
import { fetchMarketRestaurant } from '../../api/restaurants';
import { fetchMealsByRestaurant } from '../../api/meals';
import { Header } from '../../layout/Header';
import { MiniAppShell } from '../../layout/MiniAppShell';
import { PRODUCT_CATEGORIES, type ProductCategory } from '../../utils/productCategories';
import { deliveryPromiseText } from '../../utils/deliveryPromise';
import categoryMarketBg from '../../assets/category-market-bg.jpg';

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

const CATEGORY_IMAGE_POSITIONS: Record<string, string> = {
  VEGETABLES_HERBS: '28% 78%',
  FRUITS_BERRIES: '80% 12%',
  DRIED_FRUITS_NUTS: '70% 18%',
  MEAT_POULTRY: '72% 78%',
  BREAD_BAKERY: '47% 93%',
  JUICES_SODAS: '88% 38%',
};

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
    '--category-image-position': CATEGORY_IMAGE_POSITIONS[category.key] ?? '70% 70%',
  } as CSSProperties;

  return (
    <button
      type="button"
      onClick={onClick}
      style={style}
      className="group relative aspect-square overflow-hidden rounded-2xl bg-[var(--category-bg)] text-left shadow-sm ring-1 ring-black/[0.03] transition-transform active:scale-[0.98]"
    >
      <img
        src={categoryMarketBg}
        alt=""
        aria-hidden="true"
        className="absolute inset-0 h-full w-full scale-110 object-cover transition-transform duration-300 group-active:scale-[1.08]"
        style={{ objectPosition: 'var(--category-image-position)' }}
      />
      <span className="absolute inset-0 bg-gradient-to-br from-white/88 via-white/42 to-white/4" />
      <span className="absolute inset-x-0 bottom-0 h-14 bg-gradient-to-t from-white/38 to-transparent" />
      <span className="relative z-10 block max-w-[78%] p-3 text-[13px] font-semibold leading-tight text-slate-950">
        {category.shortLabel}
      </span>
      <span className="absolute bottom-3 left-3 h-1.5 w-8 rounded-full bg-[var(--category-accent)]/80" />
    </button>
  );
}
