import type { AppRole, AuthSession } from '../types/domain';
import { apiJson, jsonRequest } from './client';

interface AuthSessionDto {
  accessToken: string;
  accessTokenExpiresAt: string;
  user: {
    id: string | number;
    telegramId?: number | null;
    username: string | null;
    displayName?: string | null;
    roles: AppRole[];
  };
}

function toSession(dto: AuthSessionDto): AuthSession {
  return {
    accessToken: dto.accessToken,
    accessTokenExpiresAt: dto.accessTokenExpiresAt,
    user: {
      id: String(dto.user.id),
      telegramId: dto.user.telegramId ?? null,
      username: dto.user.username,
      displayName: dto.user.displayName?.trim() || dto.user.username?.trim() || `Пользователь ${dto.user.id}`,
      roles: dto.user.roles,
    },
  };
}

export async function loginWithTelegram(initDataRaw: string, role: AppRole): Promise<AuthSession> {
  const dto = await apiJson<AuthSessionDto>(
    '/auth/telegram',
    jsonRequest('POST', { initDataRaw, role }),
    { auth: false, retryOn401: false },
  );
  return toSession(dto);
}

export async function refreshSession(): Promise<AuthSession> {
  const dto = await apiJson<AuthSessionDto>(
    '/auth/refresh',
    { method: 'POST' },
    { auth: false, retryOn401: false },
  );
  return toSession(dto);
}

export function logoutSession(): Promise<void> {
  return apiJson<void>('/auth/logout', { method: 'POST' }, { auth: false, retryOn401: false });
}
