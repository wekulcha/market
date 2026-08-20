declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData?: string;
        initDataUnsafe?: { start_param?: string; user?: { id?: number; username?: string } };
        ready: () => void;
        expand?: () => void;
        colorScheme?: 'light' | 'dark';
        themeParams?: Record<string, string | undefined>;
        requestContact?: (callback?: (shared: boolean) => void) => void;
      };
    };
  }
}

const THEME_PROPERTIES: Record<string, string> = {
  bg_color: '--tg-theme-bg-color',
  secondary_bg_color: '--tg-theme-secondary-bg-color',
  text_color: '--tg-theme-text-color',
  hint_color: '--tg-theme-hint-color',
  link_color: '--tg-theme-link-color',
  button_color: '--tg-theme-button-color',
  button_text_color: '--tg-theme-button-text-color',
  header_bg_color: '--tg-theme-header-bg-color',
  bottom_bar_bg_color: '--tg-theme-bottom-bar-bg-color',
};

function getEncodedParam(source: string, key: string): string {
  const prefix = `${key}=`;
  const part = source.replace(/^[?#]/, '').split('&').find((item) => item.startsWith(prefix));
  if (!part) return '';
  try {
    return decodeURIComponent(part.slice(prefix.length).replace(/\+/g, '%20'));
  } catch {
    return '';
  }
}

export function getTelegramInitData(): string {
  if (typeof window === 'undefined') return '';
  const direct = window.Telegram?.WebApp?.initData;
  if (direct) return direct;
  return (
    getEncodedParam(window.location.hash, 'tgWebAppData') ||
    getEncodedParam(window.location.search, 'tgWebAppData')
  );
}

export function initTelegramWebApp(): void {
  const webApp = typeof window === 'undefined' ? undefined : window.Telegram?.WebApp;
  if (!webApp) return;
  webApp.ready();
  try {
    webApp.expand?.();
  } catch {
    // Some desktop Telegram builds can reject expand during startup.
  }
  document.documentElement.dataset.telegramTheme = webApp.colorScheme ?? 'light';
  Object.entries(webApp.themeParams ?? {}).forEach(([key, value]) => {
    const property = THEME_PROPERTIES[key];
    if (property && value) document.documentElement.style.setProperty(property, value);
  });
}

export async function waitForTelegramInitData(maxWaitMs = 5_000): Promise<string> {
  const deadline = Date.now() + maxWaitMs;
  while (Date.now() < deadline) {
    const value = getTelegramInitData();
    if (value) return value;
    await new Promise((resolve) => window.setTimeout(resolve, 50));
  }
  return getTelegramInitData();
}

export function requestTelegramContact(): Promise<boolean> {
  const requestContact = typeof window === 'undefined' ? undefined : window.Telegram?.WebApp?.requestContact;
  if (!requestContact) return Promise.resolve(false);
  return new Promise((resolve) => {
    try {
      requestContact((shared) => resolve(Boolean(shared)));
    } catch {
      resolve(false);
    }
  });
}
