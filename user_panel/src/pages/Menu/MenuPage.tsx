import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { fetchMarketRestaurant } from '../../api/restaurants';
import { fetchMealsByRestaurant } from '../../api/meals';
import { MenuItemCard } from '../../components/menu/MenuItemCard';
import { useAppContext } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { BottomBarCart } from '../../layout/BottomBarCart';
import { Header } from '../../layout/Header';
import { MiniAppShell } from '../../layout/MiniAppShell';
import type { Meal } from '../../types/meal';
import { formatLocationShort } from '../../utils/locationFormat';
import {
  PRODUCT_CATEGORY_KEYS,
  findProductCategory,
  productCategoryLabel,
  productCategoryRank,
  productCategoryShortLabel,
} from '../../utils/productCategories';

export function MenuPage() {
  const { categoryKey } = useParams<{ categoryKey?: string }>();
  const navigate = useNavigate();
  const { selectedRestaurant, setSelectedRestaurant, setServiceType } = useAppContext();
  const { currentUser } = useAuth();
  const [meals, setMeals] = useState<Meal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const categoryRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const selectedCategory = findProductCategory(categoryKey)?.key ?? null;
  const selectedCategoryInfo = findProductCategory(selectedCategory);
  const deliveryAddressLabel = formatLocationShort(currentUser?.address ?? null);

  const loadProducts = async () => {
    try {
      setLoading(true);
      setError(null);
      const restaurant = selectedRestaurant ?? (await fetchMarketRestaurant());
      setSelectedRestaurant(restaurant);
      setServiceType('DELIVERY');
      const data = await fetchMealsByRestaurant(restaurant.id);
      setMeals(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadProducts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRestaurant?.id]);

  const normalizedSearch = searchQuery.toLowerCase().trim();
  const mealsAfterSearch = useMemo(() => {
    const available = meals.filter((meal) => meal.is_available);
    if (!normalizedSearch) return available;
    return available.filter((meal) => {
      const haystack = [meal.name, meal.description ?? '', productCategoryLabel(meal.category)]
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalizedSearch);
    });
  }, [meals, normalizedSearch]);

  const visibleMeals = useMemo(() => {
    if (!selectedCategory) return mealsAfterSearch;
    return mealsAfterSearch.filter((meal) => meal.category === selectedCategory);
  }, [mealsAfterSearch, selectedCategory]);

  const categories = PRODUCT_CATEGORY_KEYS;

  const groupedMeals = useMemo(() => {
    const grouped: Record<string, Meal[]> = {};
    for (const meal of visibleMeals) {
      const category = meal.category || 'OTHER';
      if (!grouped[category]) grouped[category] = [];
      grouped[category].push(meal);
    }
    return grouped;
  }, [visibleMeals]);

  const categoriesToRender = useMemo(() => {
    if (selectedCategory) return [selectedCategory];
    return Array.from(new Set(visibleMeals.map((meal) => meal.category).filter(Boolean) as string[])).sort(
      (a, b) => {
        const rankDiff = productCategoryRank(a) - productCategoryRank(b);
        if (rankDiff !== 0) return rankDiff;
        return a.localeCompare(b, 'ru');
      }
    );
  }, [selectedCategory, visibleMeals]);

  const handleRetry = () => {
    void loadProducts();
  };

  const handleCategoryClick = (cat: string) => {
    if (cat !== selectedCategory) {
      navigate(`/catalog/${cat}`);
      return;
    }

    const el = categoryRefs.current[cat];
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <MiniAppShell>
      <div className="space-y-4 pb-24">
        <Header
          title={selectedCategoryInfo?.label ?? 'Каталог'}
          showBack
          onBackClick={() => navigate('/catalog')}
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

        <div className="bg-slate-100 rounded-full px-4 py-2">
          <span className="text-sm text-slate-700">
            Доставка: {deliveryAddressLabel || 'адрес можно указать при оформлении'}
          </span>
        </div>

        {!loading && !error && (
          <div className="sticky top-14 z-20 -mx-4 px-4 py-2 bg-neutral-50/95 backdrop-blur-sm border-b border-slate-200">
            <div className="flex gap-2 overflow-x-auto scrollbar-hide">
              {categories.map((cat) => {
                const isActive = selectedCategory === cat;
                return (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => handleCategoryClick(cat)}
                    className={
                      'whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium border transition-colors ' +
                      (isActive
                        ? 'bg-slate-900 text-white border-slate-900'
                        : 'bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200')
                    }
                  >
                    {productCategoryShortLabel(cat)}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {loading && (
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="bg-white rounded-2xl shadow-sm p-3 flex gap-3 animate-pulse"
              >
                <div className="w-20 h-20 bg-slate-100 rounded-xl" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-slate-200 rounded w-3/4" />
                  <div className="h-3 bg-slate-200 rounded w-1/2" />
                  <div className="h-3 bg-slate-200 rounded w-1/4" />
                </div>
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center py-12 px-4">
            <p className="text-sm text-slate-600 text-center mb-4">
              Не удалось загрузить товары. Попробуйте позже.
            </p>
            <button
              onClick={handleRetry}
              className="px-4 py-2 bg-slate-900 text-white rounded-2xl text-sm font-medium hover:bg-slate-800 transition-colors"
            >
              Попробовать снова
            </button>
          </div>
        )}

        {!loading && !error && (
          <div className="mt-3 space-y-4 pb-28">
            {visibleMeals.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-sm">
                {searchQuery.trim()
                  ? 'Ничего не найдено. Попробуйте изменить запрос.'
                  : selectedCategory
                    ? 'В этой категории пока нет товаров'
                    : 'Нет доступных товаров'}
              </div>
            ) : (
              categoriesToRender.map((cat) => {
                const mealsInCat = groupedMeals[cat] ?? [];
                if (mealsInCat.length === 0) return null;

                return (
                  <div
                    key={cat}
                    ref={(el) => {
                      categoryRefs.current[cat] = el;
                    }}
                    className="space-y-2"
                  >
                    <div className="text-sm font-semibold text-slate-800 px-1">
                      {productCategoryLabel(cat)}
                    </div>
                    <div className="space-y-3">
                      {mealsInCat.map((meal) => (
                        <MenuItemCard key={meal.id} meal={meal} />
                      ))}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      <BottomBarCart />
    </MiniAppShell>
  );
}
