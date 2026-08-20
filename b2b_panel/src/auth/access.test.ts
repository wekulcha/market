import { describe, expect, it } from 'vitest';
import { canAccessRole, canBrowseCatalog, canCheckout, roleFromPath } from './access';
import type { BuyerSubscription } from '../types/domain';

function subscription(
  status: BuyerSubscription['status'],
  accessPolicy: BuyerSubscription['accessPolicy'],
): BuyerSubscription {
  return {
    status,
    accessPolicy,
    planName: null,
    amountKopecks: null,
    currency: 'RUB',
    expiresAt: null,
    autoRenew: false,
  };
}

describe('role access guard', () => {
  it('не смешивает buyer и seller пространства', () => {
    expect(canAccessRole(['BUYER'], 'BUYER')).toBe(true);
    expect(canAccessRole(['BUYER'], 'SELLER')).toBe(false);
    expect(canAccessRole(['SELLER'], 'BUYER')).toBe(false);
  });

  it('пускает SUPERADMIN в admin пространство', () => {
    expect(canAccessRole(['SUPERADMIN'], 'ADMIN')).toBe(true);
    expect(canAccessRole(['ADMIN'], 'ADMIN')).toBe(true);
  });

  it('определяет роль только по первому сегменту маршрута', () => {
    expect(roleFromPath('/buyer/orders')).toBe('BUYER');
    expect(roleFromPath('/seller/offers/1/edit')).toBe('SELLER');
    expect(roleFromPath('/admin/audit')).toBe('ADMIN');
  });
});

describe('subscription guard', () => {
  it('показывает teaser без возможности checkout', () => {
    const value = subscription('NONE', 'TEASER');
    expect(canBrowseCatalog(value)).toBe(true);
    expect(canCheckout(value)).toBe(false);
  });

  it('разрешает checkout только действующему доступу FULL', () => {
    expect(canCheckout(subscription('ACTIVE', 'FULL'))).toBe(true);
    expect(canCheckout(subscription('TRIAL', 'FULL'))).toBe(true);
    expect(canCheckout(subscription('PAST_DUE', 'FULL'))).toBe(true);
    expect(canCheckout(subscription('ACTIVE', 'READ_ONLY'))).toBe(false);
    expect(canCheckout(subscription('EXPIRED', 'FULL'))).toBe(false);
  });
});
