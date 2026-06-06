import { BASE_URL } from '../api/baseUrl';

export function mealImageUrl(link: string | null | undefined): string {
  if (link == null || link === '') return '';
  if (link.startsWith('http://') || link.startsWith('https://') || link.startsWith('data:')) {
    return link;
  }
  const path = link.startsWith('/') ? link : `/${link}`;
  try {
    const origin = new URL(BASE_URL, typeof window !== 'undefined' ? window.location.href : 'http://localhost').origin;
    return origin + path;
  } catch {
    return path;
  }
}
