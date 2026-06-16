import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { User } from '../types/user';
import {
  loginWithBotToken,
  loginWithTelegram,
  logoutSession,
  refreshSession,
  type AuthSession,
} from '../api/auth';
import { ApiError, configureApiClient, resetApiClient } from '../api/client';
import { getBotAuthToken, waitForTelegramInitData } from '../telegram/initTelegram';

interface AuthContextValue {
  currentUser: User | null;
  accessToken: string | null;
  authReady: boolean;
  authError: string | null;
  reloadAuth: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

type ResolveReason = 'no_telegram_context' | 'telegram_auth_failed' | 'network';

type ResolveResult =
  | { ok: true; session: AuthSession }
  | { ok: false; reason: ResolveReason };

function resolveErrorMessage(reason: ResolveReason): string {
  if (reason === 'no_telegram_context') {
    return 'Откройте мини-приложение из Telegram через кнопку в боте Kulcha Market.';
  }
  if (reason === 'telegram_auth_failed') {
    return 'Не удалось подтвердить Telegram-сессию. Закройте и заново откройте мини-приложение из бота Kulcha Market.';
  }
  return 'Не удалось подключиться к серверу. Попробуйте позже.';
}

async function resolveSession(): Promise<ResolveResult> {
  try {
    const refreshed = await refreshSession();
    return { ok: true, session: refreshed };
  } catch {
    // Refresh cookie may be absent or expired. Fall through to Telegram login.
  }

  const botToken = getBotAuthToken();
  if (botToken) {
    try {
      const loggedIn = await loginWithBotToken(botToken);
      return { ok: true, session: loggedIn };
    } catch {
      // Expired/invalid bot token: fall through to Telegram initData.
    }
  }

  let initData = await waitForTelegramInitData(4500, 50);
  if (!initData) {
    await new Promise((resolve) => setTimeout(resolve, 250));
    initData = await waitForTelegramInitData(3500, 50);
  }
  if (!initData) {
    return { ok: false, reason: 'no_telegram_context' };
  }

  try {
    const loggedIn = await loginWithTelegram(initData);
    return { ok: true, session: loggedIn };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return { ok: false, reason: 'telegram_auth_failed' };
    }
    return { ok: false, reason: 'network' };
  }
}

export const AuthContextProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const accessTokenRef = useRef<string | null>(null);

  const applySession = useCallback((session: AuthSession | null) => {
    const nextToken = session?.accessToken ?? null;
    accessTokenRef.current = nextToken;
    setAccessToken(nextToken);
    setCurrentUser(session?.user ?? null);
    if (session) {
      setAuthError(null);
    }
  }, []);

  const clearSession = useCallback((errorMessage: string | null) => {
    accessTokenRef.current = null;
    setAccessToken(null);
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

  const logout = useCallback(() => {
    void logoutSession()
      .catch(() => {})
      .finally(() => {
        clearSession(null);
        setAuthReady(true);
      });
  }, [clearSession]);

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
    <AuthContext.Provider
      value={{ currentUser, accessToken, authReady, authError, reloadAuth, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthContextProvider');
  }
  return ctx;
}
