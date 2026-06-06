import { MARKET_BRAND_NAME } from '../config/market';

interface HeaderProps {
  title?: string;
  /** Слева: три полоски (главная/меню), если нет showBack */
  onBurgerClick?: () => void;
  /** Справа: иконка профиля (нужна вместе с showBack — иначе «бургер» скрыт) */
  onProfileClick?: () => void;
  /** Справа: «домой» / каталог (например на экране профиля) */
  onHomeClick?: () => void;
  onSearchClick?: () => void;
  showSearch?: boolean;
  showBack?: boolean;
  onBackClick?: () => void;
}

export function Header({
  title = MARKET_BRAND_NAME,
  onBurgerClick,
  onProfileClick,
  onHomeClick,
  onSearchClick,
  showSearch = true,
  showBack = false,
  onBackClick,
}: HeaderProps) {
  const handleLeftClick = () => {
    if (showBack && onBackClick) {
      onBackClick();
    } else if (onBurgerClick) {
      onBurgerClick();
    }
  };

  const handleSearchClick = () => {
    if (onSearchClick) {
      onSearchClick();
    }
  };

  const rightHasSearch = Boolean(showSearch && onSearchClick);
  const rightHasProfile = Boolean(onProfileClick);
  const rightHasHome = Boolean(onHomeClick);

  return (
    <header className="sticky top-0 z-30 h-14 flex items-center justify-between px-2 border-b border-slate-200 bg-white/95 backdrop-blur-sm rounded-t-lg">
      <button
        type="button"
        onClick={handleLeftClick}
        className="p-2 hover:bg-slate-100 rounded-lg transition-colors shrink-0"
        aria-label={showBack ? 'Назад' : 'Меню'}
      >
        {showBack ? (
          <svg className="w-6 h-6 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        ) : (
          <svg className="w-6 h-6 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        )}
      </button>

      <h1 className="text-base font-semibold text-slate-900 truncate text-center flex-1 min-w-0 px-2">{title}</h1>

      <div className="flex items-center justify-end shrink-0">
        {rightHasHome && (
          <button
            type="button"
            onClick={onHomeClick}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            aria-label="К каталогу"
          >
            <svg className="w-6 h-6 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
              />
            </svg>
          </button>
        )}
        {rightHasProfile && (
          <button
            type="button"
            onClick={onProfileClick}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            aria-label="Профиль"
          >
            <svg className="w-6 h-6 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
              />
            </svg>
          </button>
        )}
        {rightHasSearch ? (
          <button
            type="button"
            onClick={handleSearchClick}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            aria-label="Поиск"
          >
            <svg className="w-6 h-6 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </button>
        ) : !rightHasProfile && !rightHasHome ? (
          <div className="w-10" />
        ) : null}
      </div>
    </header>
  );
}
