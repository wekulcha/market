import { Outlet } from 'react-router-dom';
import { MobileShell } from '../../components/MobileShell';

const sellerNavigation = [
  { to: '/seller', label: 'Профиль', icon: '○', end: true },
  { to: '/seller/offers', label: 'Партии', icon: '▦' },
  { to: '/seller/offers/new', label: 'Создать', icon: '+' },
  { to: '/seller/orders', label: 'Заказы', icon: '≡' },
];

export function SellerShell() {
  return (
    <MobileShell roleLabel="Кабинет поставщика" nav={sellerNavigation}>
      <Outlet />
    </MobileShell>
  );
}
