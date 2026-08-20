import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';

const navigation = [
  { to: '/admin', label: 'Dashboard', icon: '◫', end: true },
  { to: '/admin/moderation', label: 'Модерация', icon: '◇' },
  { to: '/admin/catalog', label: 'Товары', icon: '▦' },
  { to: '/admin/sellers', label: 'Поставщики', icon: 'S' },
  { to: '/admin/buyers', label: 'Покупатели', icon: 'B' },
  { to: '/admin/subscriptions', label: 'Подписки', icon: '₽' },
  { to: '/admin/orders', label: 'Заказы', icon: '≡' },
  { to: '/admin/delivery', label: 'Доставка', icon: '→' },
  { to: '/admin/invites', label: 'Приглашения', icon: '+' },
  { to: '/admin/notifications', label: 'Уведомления', icon: '•' },
  { to: '/admin/audit', label: 'Audit log', icon: '⌁' },
  { to: '/admin/settings', label: 'Настройки', icon: '⚙' },
];

export function AdminShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { user } = useAuth();
  return (
    <div className="admin-stage">
      <div className="admin-layout">
        <aside className={`admin-sidebar${menuOpen ? ' is-open' : ''}`}>
          <NavLink className="brand" to="/admin" onClick={() => setMenuOpen(false)}>
            <span className="brand__mark">K</span>
            <span><strong>KULCHA B2B</strong><small>Панель администратора</small></span>
          </NavLink>
          <nav className="admin-nav" aria-label="Разделы админ-панели">
            {navigation.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) => `admin-nav__item${isActive ? ' is-active' : ''}`}
              >
                <span aria-hidden="true">{item.icon}</span><span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="admin-sidebar__footer">Role-isolated API · Europe/Moscow</div>
        </aside>
        <div className="admin-main">
          <header className="admin-topbar">
            <button className="admin-menu-button" type="button" aria-label="Открыть меню" onClick={() => setMenuOpen((value) => !value)}>☰</button>
            <span className="live-dot"><i /> Система онлайн</span>
            <div className="admin-user"><span>{user?.displayName ?? 'Администратор'}</span><i>{(user?.displayName ?? 'A').slice(0, 1).toUpperCase()}</i></div>
          </header>
          <main className="admin-content"><Outlet /></main>
        </div>
      </div>
    </div>
  );
}
