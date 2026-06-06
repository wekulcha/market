import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { MARKET_BRAND_NAME, selectMarketRestaurant } from "../../config/market";
import { AdminHeader } from "../../layout/AdminHeader";
import { useAuth } from "../../context/AuthContext";

export const AdminCafeListPage: React.FC = () => {
  const navigate = useNavigate();
  const { restaurants, authError, authReady } = useAuth();

  useEffect(() => {
    if (!authReady || authError) return;
    const marketRestaurant = selectMarketRestaurant(restaurants);
    if (!marketRestaurant) return;

    navigate(`/restaurants/${marketRestaurant.id}`, {
      replace: true,
      state: { restaurantName: marketRestaurant.name || MARKET_BRAND_NAME },
    });
  }, [authError, authReady, navigate, restaurants]);

  return (
    <>
      <AdminHeader
        title={MARKET_BRAND_NAME}
        showBack={false}
        onBurgerClick={() => navigate("/profile")}
        showSearch={false}
      />

      <main className="flex-1 overflow-y-auto px-4 md:px-6 lg:px-8 pt-3 md:pt-4 pb-6 bg-gradient-to-b from-slate-50 to-slate-100">
        {!authReady && (
          <div className="text-sm text-slate-500">Проверка доступа...</div>
        )}

        {authReady && authError && (
          <div className="mb-4 p-3 bg-amber-50 rounded-2xl border border-amber-100 text-sm text-amber-900">
            {authError}
          </div>
        )}

        {authReady && !authError && restaurants.length === 0 && (
          <div className="text-sm text-slate-500 mt-6 text-center">
            Магазин пока не привязан к вашему аккаунту.
          </div>
        )}
      </main>
    </>
  );
};

