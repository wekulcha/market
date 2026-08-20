import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';

export interface MobileNavItem {
  to: string;
  label: string;
  icon: string;
  end?: boolean;
}

export function MobileShell({
  roleLabel,
  nav,
  children,
}: {
  roleLabel: string;
  nav: MobileNavItem[];
  children: ReactNode;
}) {
  return (
    <div className="mobile-stage">
      <div className="mobile-shell">
        <header className="mobile-topbar">
          <NavLink className="brand" to={nav[0]?.to ?? '/'}>
            <span className="brand__mark">K</span>
            <span>
              <strong>KULCHA B2B</strong>
              <small>{roleLabel}</small>
            </span>
          </NavLink>
          <span className="live-dot"><i /> Онлайн</span>
        </header>
        <main className="mobile-content">{children}</main>
        <nav className="bottom-nav" aria-label="Основная навигация">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `bottom-nav__item${isActive ? ' is-active' : ''}`}
            >
              <span aria-hidden="true">{item.icon}</span>
              <small>{item.label}</small>
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}
