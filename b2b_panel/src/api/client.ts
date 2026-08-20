const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '');
const DEFAULT_TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail || `HTTP ${status}`);
    this.name = 'ApiError';
  }
}

interface ApiOptions {
  auth?: boolean;
  retryOn401?: boolean;
  timeoutMs?: number;
}

interface AuthAdapter {
  getAccessToken: () => string | null;
  refreshAccessToken: () => Promise<string | null>;
  onAuthFailure: () => void;
}

const emptyAuth: AuthAdapter = {
  getAccessToken: () => null,
  refreshAccessToken: async () => null,
  onAuthFailure: () => undefined,
};

let authAdapter = emptyAuth;
let refreshPromise: Promise<string | null> | null = null;

export function configureApiAuth(next: AuthAdapter): () => void {
  authAdapter = next;
  return () => {
    authAdapter = emptyAuth;
    refreshPromise = null;
  };
}

function urlFor(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

async function errorDetail(response: Response): Promise<string> {
  const body = await response.text().catch(() => '');
  if (!body) return `Ошибка запроса (${response.status})`;
  try {
    const parsed = JSON.parse(body) as {
      detail?: unknown;
      message?: unknown;
      error?: { message?: unknown };
    };
    if (typeof parsed.detail === 'string') return parsed.detail;
    if (typeof parsed.message === 'string') return parsed.message;
    if (typeof parsed.error?.message === 'string') return parsed.error.message;
  } catch {
    // Plain text is a valid error response.
  }
  return body.slice(0, 800);
}

async function refreshOnce(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = authAdapter.refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
  options: ApiOptions = {},
): Promise<Response> {
  const auth = options.auth ?? true;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), options.timeoutMs ?? DEFAULT_TIMEOUT_MS);

  const execute = () => {
    const headers = new Headers(init.headers);
    const token = auth ? authAdapter.getAccessToken() : null;
    if (token) headers.set('Authorization', `Bearer ${token}`);
    return fetch(urlFor(path), {
      ...init,
      headers,
      credentials: 'include',
      signal: controller.signal,
    });
  };

  try {
    let response = await execute();
    if (auth && response.status === 401 && (options.retryOn401 ?? true)) {
      const nextToken = await refreshOnce();
      if (nextToken) response = await execute();
      else authAdapter.onAuthFailure();
    }
    return response;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function apiJson<T>(
  path: string,
  init: RequestInit = {},
  options: ApiOptions = {},
): Promise<T> {
  const response = await apiFetch(path, init, options);
  if (!response.ok) throw new ApiError(response.status, await errorDetail(response));
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function jsonRequest(method: string, value?: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: value === undefined ? undefined : JSON.stringify(value),
  };
}
