import type { User } from '../types/user';
import { apiFetchJson } from './client';
import { toUser } from './users';

interface AuthUserDto {
  id: number;
  username: string;
  phone: string;
  email: string | null;
  address: string | null;
  registeredAt: string;
}

interface AuthSessionDto {
  accessToken: string;
  accessTokenExpiresAt: string;
  user: AuthUserDto;
}

export interface AuthSession {
  accessToken: string;
  accessTokenExpiresAt: string;
  user: User;
}

function toSession(dto: AuthSessionDto): AuthSession {
  return {
    accessToken: dto.accessToken,
    accessTokenExpiresAt: dto.accessTokenExpiresAt,
    user: toUser(dto.user),
  };
}

export async function loginWithTelegram(initDataRaw: string): Promise<AuthSession> {
  const dto = await apiFetchJson<AuthSessionDto>(
    '/auth/telegram/user',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initDataRaw }),
    },
    { retryOn401: false }
  );
  return toSession(dto);
}

export async function loginWithBotToken(token: string): Promise<AuthSession> {
  const dto = await apiFetchJson<AuthSessionDto>(
    '/auth/bot/user',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    },
    { retryOn401: false }
  );
  return toSession(dto);
}

export async function refreshSession(): Promise<AuthSession> {
  const dto = await apiFetchJson<AuthSessionDto>(
    '/auth/refresh',
    { method: 'POST' },
    { retryOn401: false }
  );
  return toSession(dto);
}

export async function logoutSession(): Promise<void> {
  await apiFetchJson<void>(
    '/auth/logout',
    { method: 'POST' },
    { retryOn401: false }
  );
}
