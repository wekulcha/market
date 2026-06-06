import { apiFetchJson } from './client';

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

export interface SuperadminUser {
  id: number;
  username: string;
  phone: string;
  email: string | null;
  address: string | null;
}

export interface AuthSession {
  accessToken: string;
  user: SuperadminUser;
}

function toSession(dto: AuthSessionDto): AuthSession {
  return {
    accessToken: dto.accessToken,
    user: {
      id: dto.user.id,
      username: dto.user.username,
      phone: dto.user.phone,
      email: dto.user.email,
      address: dto.user.address,
    },
  };
}

export async function loginWithTelegram(initDataRaw: string): Promise<AuthSession> {
  const dto = await apiFetchJson<AuthSessionDto>(
    '/auth/telegram/superadmin',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initDataRaw }),
    },
    { retryOn401: false }
  );
  return toSession(dto);
}
