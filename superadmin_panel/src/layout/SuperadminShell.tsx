import { Outlet, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function SuperadminShell() {
  const { currentUser, authReady, authError, reloadAuth } = useAuth();

  if (!authReady) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 text-center space-y-2">
          <div className="text-sm text-slate-600">Проверяем вход через Telegram...</div>
          <div className="text-xs text-slate-400">Пожалуйста, подождите</div>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 text-center space-y-3 max-w-sm">
          <div className="text-lg font-semibold text-slate-900">Superadmin</div>
          <div className="text-sm text-red-600">
            {authError ?? "Нет доступа."}
          </div>
          <button
            type="button"
            onClick={reloadAuth}
            className="px-4 py-2 bg-slate-900 text-white rounded-xl text-sm font-medium hover:bg-slate-800"
          >
            Повторить
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100">
      <nav className="bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-4">
        <Link to="/" className="text-sm font-semibold text-slate-800 hover:text-slate-900">
          Магазины
        </Link>
        <Link to="/users" className="text-sm font-semibold text-slate-800 hover:text-slate-900">
          Пользователи
        </Link>
        <Link to="/orders" className="text-sm font-semibold text-slate-800 hover:text-slate-900">
          Заказы
        </Link>
        <Link to="/analytics" className="text-sm font-semibold text-slate-800 hover:text-slate-900">
          Аналитика
        </Link>
        <Link to="/tools" className="text-sm font-semibold text-slate-800 hover:text-slate-900">
          Инструменты
        </Link>
        <div className="ml-auto text-xs text-slate-400">
          {currentUser.username}
        </div>
      </nav>
      <main className="p-4 max-w-4xl mx-auto">
        <Outlet />
      </main>
    </div>
  );
}
