export interface User {
  id: number;
  username: string;
  phone: string;
  telegram_id: number | null;
  email: string | null;
  address: string | null;
  registered_at: string;
}
