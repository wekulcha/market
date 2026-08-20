import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { AuthContext, type AuthContextValue } from '../auth/AuthContext';
import type { AppRole } from '../types/domain';
import { AppRoutes } from './App';

afterEach(cleanup);

function renderRoute(path: string, roles: AppRole[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const auth: AuthContextValue = {
    user: {
      id: 'test-user',
      telegramId: 1,
      username: 'tester',
      displayName: 'Тестовый пользователь',
      roles,
    },
    accessToken: 'test-token',
    loading: false,
    error: null,
    retry: () => undefined,
    logout: () => undefined,
  };
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AuthContext.Provider value={auth}>
          <AppRoutes />
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('role route smoke', () => {
  it('открывает buyer subtree', () => {
    renderRoute('/buyer/catalog', ['BUYER']);
    expect(screen.getByText('Кабинет покупателя')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Каталог/ })).toBeInTheDocument();
  });

  it('открывает seller subtree', () => {
    renderRoute('/seller/offers', ['SELLER']);
    expect(screen.getByText('Кабинет поставщика')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Партии/ })).toBeInTheDocument();
  });

  it('открывает admin subtree для SUPERADMIN', () => {
    renderRoute('/admin/audit', ['SUPERADMIN']);
    expect(screen.getByText('Панель администратора')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Audit log/ })).toBeInTheDocument();
  });

  it('перенаправляет seller из buyer subtree', async () => {
    renderRoute('/buyer/orders', ['SELLER']);
    expect(await screen.findByText('Кабинет поставщика')).toBeInTheDocument();
  });
});
