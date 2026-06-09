import { apiFetchJson } from './client';

export function logUserActivity(event: string, metadata?: Record<string, unknown>): void {
  void apiFetchJson<void>(
    '/activity',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event, source: 'webapp', metadata: metadata ?? {} }),
    },
    { auth: true, timeoutMs: 5000 }
  ).catch(() => {});
}
