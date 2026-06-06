import React from "react";
import { useNavigate } from "react-router-dom";
import { AdminHeader } from "../../layout/AdminHeader";
import { useAuth } from "../../context/AuthContext";

export const AdminProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const { user, authError, authReady } = useAuth();

  return (
    <>
      <AdminHeader
        title="Профиль"
        showBack
        onBackClick={() => navigate("/")}
        onBurgerClick={() => navigate("/")}
        showSearch={false}
      />

      <main className="flex-1 overflow-y-auto px-4 pt-3 pb-6 bg-gradient-to-b from-slate-50 to-slate-100 space-y-4">
        {authReady && authError && (
          <section className="bg-amber-50 rounded-3xl p-3 border border-amber-100 text-sm text-amber-900">
            {authError}
          </section>
        )}

        <section className="bg-white rounded-3xl p-3 shadow-sm border border-slate-100 space-y-2">
          <div className="text-sm font-semibold text-slate-900">Аккаунт сотрудника</div>
          <div className="text-xs text-slate-500">
            Вход выполняется автоматически по данным Telegram при открытии панели из бота.
          </div>
          {user && (
            <div className="mt-2 space-y-2 text-sm">
              <div className="flex justify-between gap-2">
                <span className="text-slate-500 shrink-0">Telegram ID</span>
                <span className="font-mono text-slate-800 text-right">
                  {user.telegram_id ?? "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Username</span>
                <span className="text-slate-800">{user.username}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Телефон</span>
                <span className="text-slate-800">{user.phone}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">User ID (БД)</span>
                <span className="font-mono text-slate-800">{user.id}</span>
              </div>
            </div>
          )}
        </section>

        <section className="bg-white rounded-3xl p-3 shadow-sm border border-slate-100 space-y-1">
          <button
            type="button"
            className="w-full flex items-center justify-between py-2 text-sm text-slate-800"
            onClick={() => alert("Политика конфиденциальности (заглушка)")}
          >
            <span>Политика конфиденциальности</span>
            <span className="text-slate-400 text-xs">›</span>
          </button>
          <button
            type="button"
            className="w-full flex items-center justify-between py-2 text-sm text-slate-800"
            onClick={() => alert("Пользовательское соглашение (заглушка)")}
          >
            <span>Пользовательское соглашение</span>
            <span className="text-slate-400 text-xs">›</span>
          </button>
        </section>
      </main>
    </>
  );
};
