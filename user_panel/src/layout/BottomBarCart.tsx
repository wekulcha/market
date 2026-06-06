import { useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';

export function BottomBarCart() {
  const navigate = useNavigate();
  const { totalItems } = useCart();

  const handleClick = () => {
    if (totalItems > 0) {
      navigate('/cart');
    }
  };

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 w-full max-w-[430px] px-4 z-20">
      <button
        onClick={handleClick}
        disabled={totalItems === 0}
        className={`w-full flex items-center justify-between rounded-full px-4 py-3 shadow-lg transition-all ${
          totalItems > 0
            ? 'bg-slate-900 text-white hover:bg-slate-800'
            : 'bg-slate-200 text-slate-500 cursor-not-allowed opacity-80'
        }`}
      >
        <div className="flex items-center gap-2">
          {/* Cart icon */}
          <div className="relative">
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"
              />
            </svg>
            {totalItems > 0 && (
              <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-semibold">
                {totalItems > 9 ? '9+' : totalItems}
              </span>
            )}
          </div>
          <span className="text-sm font-medium">
            {totalItems > 0 ? 'Продолжить' : 'Корзина'}
          </span>
        </div>
      </button>
    </div>
  );
}

