import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { loginWithTelegram, logoutSession, refreshSession } from '../api/auth';
import { configureApiAuth } from '../api/client';
import { waitForTelegramInitData } from '../telegram/webApp';
import type { AppRole, AuthSession, AuthUser } from '../types/domain';
import { roleFromPath } from './access';

export interface AuthContextValue {
  user: AuthUser | null;
  accessToken: string | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

async function resolveSession(role: AppRole): Promise<AuthSession> {
  try {
    return await refreshSession();
  } catch {
    const initData = await waitForTelegramInitData();
    if (!initData) throw new Error('Откройте этот раздел из соответствующего Telegram-бота.');
    return loginWithTelegram(initData, role);
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const tokenRef = useRef<string | null>(null);
  const requestId = useRef(0);

  const applySession = useCallback((session: AuthSession | null) => {
    tokenRef.current = session?.accessToken ?? null;
    setAccessToken(session?.accessToken ?? null);
    setUser(session?.user ?? null);
  }, []);

  const load = useCallback(async () => {
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const session = await resolveSession(roleFromPath(window.location.pathname));
      if (currentRequest === requestId.current) applySession(session);
    } catch (caught) {
      if (currentRequest === requestId.current) {
        applySession(null);
        setError(caught instanceof Error ? caught.message : 'Не удалось выполнить вход.');
      }
    } finally {
      if (currentRequest === requestId.current) setLoading(false);
    }
  }, [applySession]);

  const renew = useCallback(async () => {
    try {
      const session = await refreshSession();
      applySession(session);
      return session.accessToken;
    } catch {
      applySession(null);
      setError('Сессия завершена. Откройте приложение заново из Telegram.');
      return null;
    }
  }, [applySession]);

  useEffect(() => configureApiAuth({
    getAccessToken: () => tokenRef.current,
    refreshAccessToken: renew,
    onAuthFailure: () => applySession(null),
  }), [applySession, renew]);

  useEffect(() => {
    void load();
    return () => {
      requestId.current += 1;
    };
  }, [load]);

  const logout = useCallback(() => {
    void logoutSession().finally(() => applySession(null));
  }, [applySession]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, accessToken, loading, error, retry: () => void load(), logout }),
    [accessToken, error, load, loading, logout, user],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}
