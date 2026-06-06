import React from "react";
import { MARKET_BRAND_NAME } from "../config/market";

interface AdminHeaderProps {
  title?: string;
  showBack?: boolean;
  onBackClick?: () => void;
  onBurgerClick?: () => void;
  onSearchClick?: () => void;
  showSearch?: boolean;
  /** Если задан — справа вместо кнопки поиска. */
  rightSlot?: React.ReactNode;
}

export const AdminHeader: React.FC<AdminHeaderProps> = ({
  title = `${MARKET_BRAND_NAME} Admin`,
  showBack = false,
  onBackClick,
  onBurgerClick,
  onSearchClick,
  showSearch = true,
  rightSlot,
}) => {
  return (
    <header className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-200">
      <button
        type="button"
        onClick={showBack ? onBackClick : onBurgerClick}
        className="w-9 h-9 rounded-full bg-slate-200 flex items-center justify-center text-slate-800 hover:bg-slate-300 transition-colors"
        aria-label={showBack ? "Назад" : "Меню"}
      >
        {showBack ? (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        ) : (
          <div className="space-y-0.5">
            <span className="block w-3 h-[2px] bg-slate-700 rounded-full" />
            <span className="block w-3 h-[2px] bg-slate-700 rounded-full" />
            <span className="block w-3 h-[2px] bg-slate-700 rounded-full" />
          </div>
        )}
      </button>

      <div className="text-sm font-semibold text-slate-900 truncate px-2 flex-1 text-center">{title}</div>

      {rightSlot != null ? (
        <div className="w-9 h-9 flex items-center justify-end">{rightSlot}</div>
      ) : showSearch ? (
        <button
          type="button"
          onClick={onSearchClick}
          className="w-9 h-9 rounded-full bg-slate-200 flex items-center justify-center hover:bg-slate-300 transition-colors"
          aria-label="Поиск"
        >
          <div className="w-3 h-3 border border-slate-700 rounded-full relative">
            <span className="block w-[6px] h-[2px] bg-slate-700 absolute -right-[2px] bottom-0 rotate-45 rounded-full" />
          </div>
        </button>
      ) : (
        <div className="w-9 h-9" />
      )}
    </header>
  );
};
