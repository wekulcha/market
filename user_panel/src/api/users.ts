import type { User } from '../types/user';
import { apiFetchJson } from './client';

interface UserDto {
  id?: number;
  telegramId?: number;
  username: string;
  phone: string;
  email: string | null;
  address: string | null;
  registeredAt: string;
}

export function toUser(dto: UserDto): User {
  const id = dto.id ?? dto.telegramId ?? 0;
  const tid = dto.id ?? dto.telegramId;
  return {
    id,
    username: dto.username,
    phone: dto.phone,
    telegram_id: tid ?? null,
    email: dto.email ?? null,
    address: dto.address ?? null,
    registered_at: dto.registeredAt,
  };
}

export async function fetchCurrentUser(): Promise<User> {
  const dto = await apiFetchJson<UserDto>('/auth/me', {}, { auth: true });
  return toUser(dto);
}

export async function updateUserProfile(
  userId: number,
  patch: Partial<Pick<User, 'address' | 'phone'>>
): Promise<User> {
  const dto = await apiFetchJson<UserDto>(
    `/users/${userId}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        telegramId: userId,
        address: patch.address ?? undefined,
        phone: patch.phone ?? undefined,
      }),
    },
    { auth: true }
  );
  return toUser(dto);
}
