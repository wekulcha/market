declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready: () => void;
        expand?: () => void;
        initData?: string;
        platform?: string;
        openLink?: (
          url: string,
          options?: {
            try_browser?: string;
            try_instant_view?: boolean;
          }
        ) => void;
        themeParams?: Record<string, string | undefined>;
      };
    };
  }
}

export function initTelegramWebApp(): void {
  if (typeof window === 'undefined' || !window.Telegram?.WebApp) return;
  const webApp = window.Telegram.WebApp;
  webApp.ready();
  try {
    if (typeof webApp.expand === 'function') webApp.expand();
  } catch {
    /* ignore */
  }
}

function getEncodedUrlParam(source: string, key: string): string {
  const prefix = `${key}=`;
  const param = source
    .replace(/^[?#]/, '')
    .split('&')
    .find((part) => part.startsWith(prefix));
  if (!param) return '';

  try {
    // Telegram signs the nested initData string; decode only the outer URL layer.
    return decodeURIComponent(param.slice(prefix.length).replace(/\+/g, '%20'));
  } catch {
    return '';
  }
}

export function getTelegramInitData(): string {
  if (typeof window === 'undefined') return '';
  const api = window.Telegram?.WebApp?.initData;
  if (api && api.length > 0) return api;
  try {
    const fromHash = getEncodedUrlParam(window.location.hash, 'tgWebAppData');
    if (fromHash) return fromHash;
    const fromSearch = getEncodedUrlParam(window.location.search, 'tgWebAppData');
    if (fromSearch) return fromSearch;
  } catch {
    /* ignore */
  }
  return '';
}

export function getTelegramPlatform(): string {
  if (typeof window === "undefined") return "";
  return window.Telegram?.WebApp?.platform ?? "";
}

export function isTelegramDesktopLike(): boolean {
  const platform = getTelegramPlatform().toLowerCase();
  if (platform === "tdesktop" || platform === "macos") {
    return true;
  }

  if (typeof navigator === "undefined") return false;
  const userAgent = navigator.userAgent.toLowerCase();
  return userAgent.includes("telegram-desktop") || userAgent.includes("telegramdesktop");
}

export function openTelegramExternalLink(url: string): boolean {
  if (typeof window === "undefined") return false;

  const openLink = window.Telegram?.WebApp?.openLink;
  if (typeof openLink === "function") {
    try {
      openLink(url, { try_browser: "chrome" });
      return true;
    } catch {
      /* ignore */
    }
  }

  const opened = window.open(url, "_blank", "noopener,noreferrer");
  return opened != null;
}

/** Wait until initData is available (Telegram can populate it shortly after load). */
export async function waitForTelegramInitData(
  maxWaitMs = 12000,
  stepMs = 50
): Promise<string> {
  const deadline = Date.now() + maxWaitMs;
  while (Date.now() < deadline) {
    const d = getTelegramInitData();
    if (d) return d;
    await new Promise((r) => setTimeout(r, stepMs));
  }
  return getTelegramInitData();
}

/**
 * Reads the bot-generated HMAC auth token from the URL.
 * The admin bot puts ?tg_auth=... in the mini-app URL so auth works in any browser.
 */
export function getBotAuthToken(): string | null {
  try {
    const sp = new URLSearchParams(window.location.search);
    const t = sp.get('tg_auth');
    if (t) return t;
    const hp = new URLSearchParams(window.location.hash.slice(1));
    const ht = hp.get('tg_auth');
    if (ht) return ht;
  } catch {
    /* ignore */
  }
  return null;
}

export function buildAdminApiJsonHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const init = getTelegramInitData();
  if (init) {
    headers['X-Telegram-Init-Data'] = init;
    headers['X-Init-Data'] = init;
  }
  return headers;
}
