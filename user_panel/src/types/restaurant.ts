export interface Restaurant {
  id: number;
  name: string;
  address: string;
  imageLink?: string | null;
  ordersAcceptTo?: string | null;
}
