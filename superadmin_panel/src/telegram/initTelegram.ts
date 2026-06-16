declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready: () => void;
        expand?: () => void;
        initData?: string;
        version?: string;
        platform?: string;
        colorScheme?: 'light' | 'dark';
        themeParams?: {
          bg_color?: string;
          text_color?: string;
          hint_color?: string;
          link_color?: string;
          button_color?: string;
          button_text_color?: string;
        };
      };
    };
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

  const directInitData = window.Telegram?.WebApp?.initData;
  if (directInitData && directInitData.length > 0) {
    return directInitData;
  }

  try {
    const fromHash = getEncodedUrlParam(window.location.hash, 'tgWebAppData');
    if (fromHash) return fromHash;

    const fromSearch = getEncodedUrlParam(window.location.search, 'tgWebAppData');
    if (fromSearch) return fromSearch;
  } catch {
    return '';
  }

  return '';
}

export async function waitForTelegramInitData(
  maxWaitMs = 12_000,
  stepMs = 50
): Promise<string> {
  const deadline = Date.now() + maxWaitMs;
  while (Date.now() < deadline) {
    const data = getTelegramInitData();
    if (data) return data;
    await new Promise((resolve) => setTimeout(resolve, stepMs));
  }
  return getTelegramInitData();
}

export function initTelegramWebApp(): void {
  if (typeof window === 'undefined' || !window.Telegram?.WebApp) {
    return;
  }

  const webApp = window.Telegram.WebApp;
  webApp.ready();

  try {
    if (typeof webApp.expand === 'function') {
      webApp.expand();
    }
  } catch {
    // ignore Telegram client quirks
  }
}
