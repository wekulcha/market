import type { AppRole, BuyerSubscription } from '../types/domain';

export function roleFromPath(pathname: string): AppRole {
  if (pathname === '/seller' || pathname.startsWith('/seller/')) return 'SELLER';
  if (pathname === '/admin' || pathname.startsWith('/admin/')) return 'ADMIN';
  return 'BUYER';
}

export function canAccessRole(userRoles: readonly AppRole[], required: AppRole): boolean {
  if (required === 'ADMIN') return userRoles.includes('ADMIN') || userRoles.includes('SUPERADMIN');
  return userRoles.includes(required);
}

export function canBrowseCatalog(subscription: BuyerSubscription): boolean {
  return subscription.status === 'ACTIVE' || ['TEASER', 'READ_ONLY', 'FULL'].includes(subscription.accessPolicy);
}

export function canCheckout(subscription: BuyerSubscription): boolean {
  return (
    subscription.accessPolicy === 'FULL'
    && ['TRIAL', 'ACTIVE', 'PAST_DUE'].includes(subscription.status)
  );
}
