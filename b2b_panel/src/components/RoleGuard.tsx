import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { canAccessRole } from '../auth/access';
import { useAuth } from '../auth/AuthContext';
import type { AppRole } from '../types/domain';
import { Button, LoadingPanel, StatePanel } from './ui';

export function RoleGuard({ required, children }: { required: AppRole; children: ReactNode }) {
  const auth = useAuth();
  const location = useLocation();
  if (auth.loading) return <LoadingPanel label="Проверяем безопасный вход…" />;
  if (!auth.user) {
    return (
      <StatePanel
        icon="↗"
        title="Откройте приложение из Telegram"
        description={auth.error ?? 'Ссылка из бота передаст данные для безопасного входа.'}
        action={<Button onClick={auth.retry}>Повторить вход</Button>}
      />
    );
  }
  if (!canAccessRole(auth.user.roles, required)) {
    const destination = auth.user.roles.includes('SELLER')
      ? '/seller'
      : auth.user.roles.some((role) => role === 'ADMIN' || role === 'SUPERADMIN')
        ? '/admin'
        : '/buyer';
    if (destination !== location.pathname) return <Navigate to={destination} replace />;
    return <StatePanel icon="×" title="Нет доступа" description="Эта роль не назначена вашему аккаунту." />;
  }
  return children;
}
