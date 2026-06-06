declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready: () => void;
        expand?: () => void;
        initData?: string;
        /** Парсированные поля initData (в т.ч. start_param для deep link). */
        initDataUnsafe?: {
          start_param?: string;
          user?: { id?: number; username?: string };
        };
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

export function getTelegramStartParam(): string {
  if (typeof window === 'undefined') return '';
  const p = window.Telegram?.WebApp?.initDataUnsafe?.start_param?.trim();
  return p || '';
}

export function getTelegramInitData(): string {
  if (typeof window === 'undefined') return '';

  const directInitData = window.Telegram?.WebApp?.initData;
  if (directInitData && directInitData.length > 0) {
    return directInitData;
  }

  try {
    const hash = window.location.hash.slice(1);
    if (hash) {
      const params = new URLSearchParams(hash);
      const fromHash = params.get('tgWebAppData');
      if (fromHash) return decodeURIComponent(fromHash);
    }

    const searchParams = new URLSearchParams(window.location.search);
    const fromSearch = searchParams.get('tgWebAppData');
    if (fromSearch) return decodeURIComponent(fromSearch);
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

  if (!webApp.themeParams) {
    return;
  }

  const theme = webApp.themeParams;
  if (theme.bg_color) {
    document.documentElement.style.setProperty('--tg-theme-bg-color', theme.bg_color);
  }
  if (theme.text_color) {
    document.documentElement.style.setProperty('--tg-theme-text-color', theme.text_color);
  }
  if (theme.hint_color) {
    document.documentElement.style.setProperty('--tg-theme-hint-color', theme.hint_color);
  }
  if (theme.link_color) {
    document.documentElement.style.setProperty('--tg-theme-link-color', theme.link_color);
  }
  if (theme.button_color) {
    document.documentElement.style.setProperty('--tg-theme-button-color', theme.button_color);
  }
  if (theme.button_text_color) {
    document.documentElement.style.setProperty(
      '--tg-theme-button-text-color',
      theme.button_text_color
    );
  }
}
