import { Outlet } from 'react-router-dom';
import { MobileShell } from '../../components/MobileShell';

const buyerNavigation = [
  { to: '/buyer', label: 'Главная', icon: '⌂', end: true },
  { to: '/buyer/catalog', label: 'Каталог', icon: '▦' },
  { to: '/buyer/cart', label: 'Корзина', icon: '◫' },
  { to: '/buyer/orders', label: 'Заказы', icon: '≡' },
  { to: '/buyer/profile', label: 'Профиль', icon: '○' },
];

export function BuyerShell() {
  return (
    <MobileShell roleLabel="Кабинет покупателя" nav={buyerNavigation}>
      <Outlet />
    </MobileShell>
  );
}
