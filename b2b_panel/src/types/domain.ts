export type AppRole = 'BUYER' | 'SELLER' | 'ADMIN' | 'SUPERADMIN';

export interface AuthUser {
  id: string;
  telegramId: number | null;
  displayName: string;
  username: string | null;
  roles: AppRole[];
}

export interface AuthSession {
  accessToken: string;
  accessTokenExpiresAt: string;
  user: AuthUser;
}

export type SubscriptionStatus =
  | 'NONE'
  | 'PENDING'
  | 'TRIAL'
  | 'ACTIVE'
  | 'PAST_DUE'
  | 'EXPIRED'
  | 'CANCELED'
  | 'BLOCKED';
export type CatalogAccessPolicy = 'BLOCKED' | 'TEASER' | 'READ_ONLY' | 'FULL';

export interface BuyerSubscription {
  status: SubscriptionStatus;
  accessPolicy: CatalogAccessPolicy;
  planName: string | null;
  amountKopecks: number | null;
  currency: 'RUB';
  expiresAt: string | null;
  autoRenew: boolean;
}

export interface BuyerAddress {
  id: string;
  label: string;
  value: string;
  isDefault: boolean;
}

export interface BuyerProfile {
  id: string;
  companyName: string;
  legalForm: string | null;
  inn: string | null;
  contactName: string;
  phone: string;
  email: string | null;
  addresses: BuyerAddress[];
  subscription: BuyerSubscription;
}

export type QuantityUnit = 'KG' | 'LITER' | 'PIECE' | 'BOX' | 'PACKAGE';

/**
 * Buyer-safe projection. Deliberately contains no procurement price,
 * supplier id/name/contact, pickup address or internal comments.
 */
export interface BuyerOffer {
  id: string;
  publicName: string;
  publicDescription: string | null;
  category: string;
  photos: string[];
  buyerUnitPriceKopecks: number | null;
  currency: 'RUB';
  unit: QuantityUnit;
  packageSize: string | null;
  availableQuantityLabel: string;
  minimumQuantity: number;
  quantityStep: number;
  shelfLife: string | null;
  storageConditions: string | null;
  deliveryTerms: string | null;
  expiresAt: string | null;
}

export interface BuyerCartLine {
  id: string;
  offer: BuyerOffer;
  quantity: number;
}

export interface BuyerCart {
  lines: BuyerCartLine[];
  itemsTotalKopecks: number;
  deliveryFeeKopecks: number | null;
  totalKopecks: number;
  currency: 'RUB';
  expiresAt: string | null;
}

export type BuyerOrderStatus =
  | 'DRAFT'
  | 'RESERVED'
  | 'PENDING_CONFIRMATION'
  | 'CONFIRMED'
  | 'SELLER_PREPARING'
  | 'READY_FOR_PICKUP'
  | 'COURIER_ASSIGNED'
  | 'PICKED_UP'
  | 'IN_DELIVERY'
  | 'DELIVERED'
  | 'COMPLETED'
  | 'CANCELED'
  | 'REFUNDED';

export interface BuyerOrder {
  id: string;
  number: string;
  status: BuyerOrderStatus;
  createdAt: string;
  deliveryAddress: string;
  deliveryWindow: string | null;
  totalKopecks: number;
  currency: 'RUB';
  itemsCount: number;
}

export type SellerVerificationStatus = 'PENDING' | 'VERIFIED' | 'SUSPENDED' | 'BLOCKED';
export interface SellerProfile {
  id: string;
  companyName: string;
  inn: string | null;
  contactName: string;
  phone: string;
  pickupAddress: string;
  verificationStatus: SellerVerificationStatus;
  /** Current backend projection name. */
  rejectionReason: string | null;
  /** Forward-compatible alias used by the canonical profile schema. */
  adminComment?: string | null;
}

export type SellerOfferStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'UNDER_REVIEW'
  | 'CHANGES_REQUESTED'
  | 'REJECTED'
  | 'APPROVED'
  | 'PUBLISHED'
  | 'PAUSED'
  | 'SOLD_OUT'
  | 'EXPIRED'
  | 'ARCHIVED';

export interface SellerOffer {
  id: string;
  name: string;
  description: string | null;
  category: string;
  photos: string[];
  procurementUnitPriceKopecks: number;
  currency: 'RUB';
  unit: QuantityUnit;
  packageSize: string | null;
  totalQuantity: number;
  reservedQuantity: number;
  availableQuantity: number;
  minimumQuantity: number;
  quantityStep: number;
  shelfLife: string | null;
  storageConditions: string | null;
  expiresAt: string | null;
  status: SellerOfferStatus;
  rejectionReason: string | null;
  updatedAt: string;
}

export interface SellerOrder {
  id: string;
  number: string;
  status: BuyerOrderStatus;
  createdAt: string;
  itemsCount: number;
  quantityLabel: string;
  pickupWindow: string | null;
}

export interface DashboardKpi {
  pendingOffers: number;
  activeOffers: number;
  inventoryValueKopecks: number;
  newOrders: number;
  gmvKopecks: number;
  markupRevenueKopecks: number;
  mrrKopecks: number;
  activeSubscribers: number;
  lowStockOffers: number;
  ordersRequiringAttention: number;
}

export interface ModerationOffer extends SellerOffer {
  sellerDisplayName: string;
  sellerId: string;
  proposedBuyerUnitPriceKopecks: number | null;
  markupType: 'PERCENT' | 'FIXED' | 'MANUAL';
  markupValue: number | null;
  fixedMarkupKopecks: number | null;
  manualBuyerUnitPriceKopecks: number | null;
  internalComment: string | null;
}

export interface AdminListItem {
  id: string;
  title: string;
  subtitle: string | null;
  status: string;
  amountKopecks?: number | null;
  createdAt?: string | null;
}

export interface InviteResult {
  id: string;
  token: string;
  deepLink: string;
  expiresAt: string;
}

export interface ApiList<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}
