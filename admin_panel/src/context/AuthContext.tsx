import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
} from "react";
import { BASE_URL } from "../api/baseUrl";
import {
  buildAdminApiJsonHeaders,
  getBotAuthToken,
  waitForTelegramInitData,
} from "../telegram/initTelegram";
import type { AdminRestaurant } from "../types/adminRestaurant";
import type { StaffPermission } from "../types/staffAccess";

interface AdminUser {
  id: number;
  username: string;
  phone: string;
  telegram_id: number | null;
}

interface AuthContextValue {
  currentUserId: number | null;
  user: AdminUser | null;
  restaurants: AdminRestaurant[];
  authReady: boolean;
  authError: string | null;
  reloadAuth: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface SessionResponse {
  user: {
    id: number;
    username: string;
    phone: string;
  };
  restaurants: {
    id: number;
    name: string;
    address: string;
    permissions: StaffPermission[];
  }[];
}

type LoadResult =
  | { ok: true; user: AdminUser; restaurants: AdminRestaurant[] }
  | {
      ok: false;
      reason: "no_telegram_context" | "no_access" | "network";
      /** Текст с сервера или сообщение об ошибке fetch (для отладки) */
      detail?: string;
    };

function parseErrorBody(text: string): string {
  try {
    const j = JSON.parse(text) as { detail?: unknown };
    if (typeof j.detail === "string") return j.detail;
  } catch {
    /* ignore */
  }
  return text.slice(0, 500);
}

async function loadSession(): Promise<LoadResult> {
  // 1. Bot-generated HMAC token в URL — работает в любом браузере
  const botToken = getBotAuthToken();
  if (botToken) {
    try {
      const resp = await fetch(`${BASE_URL}/auth/verify-admin-bot-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: botToken }),
      });
      if (resp.ok) {
        const data = (await resp.json()) as SessionResponse;
        return {
          ok: true,
          user: {
            id: data.user.id,
            username: data.user.username,
            phone: data.user.phone,
            telegram_id: data.user.id,
          },
          restaurants: (data.restaurants ?? []).map((r) => ({
            id: r.id,
            name: r.name,
            address: r.address,
            permissions: r.permissions ?? [],
          })),
        };
      } else if (resp.status === 403) {
        const t = await resp.text();
        return { ok: false, reason: "no_access", detail: parseErrorBody(t) };
      }
      // 401/expired — fall through to initData
    } catch {
      // сеть / abort — пробуем initData ниже
    }
  }

  // 2. Telegram WebApp initData
  let init = await waitForTelegramInitData();
  // Telegram Desktop иногда заполняет initData с задержкой после первого кадра
  if (!init) {
    await new Promise((r) => setTimeout(r, 400));
    init = await waitForTelegramInitData(8000, 50);
  }
  if (!init) {
    return { ok: false, reason: "no_telegram_context" };
  }
  try {
    const resp = await fetch(`${BASE_URL}/auth/webapp-admin`, {
      method: "POST",
      headers: buildAdminApiJsonHeaders(),
      body: JSON.stringify({}),
    });
    if (!resp.ok) {
      const t = await resp.text();
      return {
        ok: false,
        reason: "no_access",
        detail: `${resp.status}: ${parseErrorBody(t)}`,
      };
    }
    const data = (await resp.json()) as SessionResponse;
    return {
      ok: true,
      user: {
        id: data.user.id,
        username: data.user.username,
        phone: data.user.phone,
        telegram_id: data.user.id,
      },
      restaurants: (data.restaurants ?? []).map((r) => ({
        id: r.id,
        name: r.name,
        address: r.address,
        permissions: r.permissions ?? [],
      })),
    };
  } catch (e) {
    return {
      ok: false,
      reason: "network",
      detail: e instanceof Error ? e.message : String(e),
    };
  }
}

export const AuthContextProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [restaurants, setRestaurants] = useState<AdminRestaurant[]>([]);
  const [authReady, setAuthReady] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const reloadAuth = useCallback(() => {
    setAuthReady(false);
    setAuthError(null);
    void loadSession()
      .then((result) => {
        if (result.ok) {
          setUser(result.user);
          setRestaurants(result.restaurants);
          setAuthError(null);
          return;
        }
        setUser(null);
        setRestaurants([]);
        if (result.reason === "no_telegram_context") {
          setAuthError(
            "Откройте панель из Telegram-бота администратора (кнопка «Открыть панель» или меню «ПАНЕЛЬ»)."
          );
        } else if (result.reason === "no_access") {
          setAuthError(
            [
              "Нет доступа. Убедитесь, что вы добавлены как сотрудник магазина, и откройте панель из бота.",
              result.detail,
            ]
              .filter(Boolean)
              .join(" ")
          );
        } else {
          setAuthError(
            ["Не удалось подключиться к серверу.", result.detail].filter(Boolean).join(" ")
          );
        }
      })
      .catch(() => {
        setAuthError("Не удалось подключиться к серверу.");
        setUser(null);
        setRestaurants([]);
      })
      .finally(() => setAuthReady(true));
  }, []);

  useEffect(() => {
    reloadAuth();
  }, [reloadAuth]);

  const currentUserId = user?.id ?? null;

  return (
    <AuthContext.Provider
      value={{
        currentUserId,
        user,
        restaurants,
        authReady,
        authError,
        reloadAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthContextProvider");
  return ctx;
}
