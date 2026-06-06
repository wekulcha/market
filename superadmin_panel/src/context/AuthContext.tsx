import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { loginWithTelegram, type AuthSession, type SuperadminUser } from '../api/auth';
import { ApiError, configureApiClient, resetApiClient } from '../api/client';
import { waitForTelegramInitData } from '../telegram/initTelegram';

interface AuthContextValue {
  currentUser: SuperadminUser | null;
  authReady: boolean;
  authError: string | null;
  reloadAuth: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

type ResolveReason = 'no_telegram_context' | 'access_denied' | 'telegram_auth_failed' | 'network';

type ResolveResult =
  | { ok: true; session: AuthSession }
  | { ok: false; reason: ResolveReason };

function resolveErrorMessage(reason: ResolveReason): string {
  if (reason === 'no_telegram_context') {
    return 'Откройте панель из Telegram через кнопку в боте Superadmin.';
  }
  if (reason === 'access_denied') {
    return 'Нет доступа. Ваш Telegram ID не в списке разработчиков.';
  }
  if (reason === 'telegram_auth_failed') {
    return 'Не удалось подтвердить Telegram-сессию. Закройте и заново откройте мини-приложение.';
  }
  return 'Не удалось подключиться к серверу. Попробуйте позже.';
}

async function resolveSession(): Promise<ResolveResult> {
  let initData = await waitForTelegramInitData(4500, 50);
  if (!initData) {
    await new Promise((resolve) => setTimeout(resolve, 250));
    initData = await waitForTelegramInitData(3500, 50);
  }
  if (!initData) {
    return { ok: false, reason: 'no_telegram_context' };
  }

  try {
    const session = await loginWithTelegram(initData);
    return { ok: true, session };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 403) return { ok: false, reason: 'access_denied' };
      if (error.status === 401) return { ok: false, reason: 'telegram_auth_failed' };
    }
    return { ok: false, reason: 'network' };
  }
}

export const AuthContextProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<SuperadminUser | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const accessTokenRef = useRef<string | null>(null);

  const applySession = useCallback((session: AuthSession | null) => {
    accessTokenRef.current = session?.accessToken ?? null;
    setCurrentUser(session?.user ?? null);
    if (session) setAuthError(null);
  }, []);

  const clearSession = useCallback((errorMessage: string | null) => {
    accessTokenRef.current = null;
    setCurrentUser(null);
    setAuthError(errorMessage);
  }, []);

  const renewAccessToken = useCallback(async (): Promise<string | null> => {
    const result = await resolveSession();
    if (result.ok) {
      applySession(result.session);
      return result.session.accessToken;
    }
    clearSession(resolveErrorMessage(result.reason));
    return null;
  }, [applySession, clearSession]);

  const reloadAuth = useCallback(() => {
    setAuthReady(false);
    setAuthError(null);

    void resolveSession()
      .then((result) => {
        if (result.ok) {
          applySession(result.session);
          return;
        }
        clearSession(resolveErrorMessage(result.reason));
      })
      .catch(() => {
        clearSession(resolveErrorMessage('network'));
      })
      .finally(() => {
        setAuthReady(true);
      });
  }, [applySession, clearSession]);

  useEffect(() => {
    configureApiClient({
      getAccessToken: () => accessTokenRef.current,
      renewAccessToken,
      onAuthFailure: () => {},
    });
    return () => {
      resetApiClient();
    };
  }, [renewAccessToken]);

  useEffect(() => {
    reloadAuth();
  }, [reloadAuth]);

  return (
    <AuthContext.Provider value={{ currentUser, authReady, authError, reloadAuth }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthContextProvider');
  return ctx;
}
