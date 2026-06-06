import { BASE_URL } from "./baseUrl";
import { AdminRestaurant } from "../types/adminRestaurant";
import { buildAdminApiJsonHeaders } from "../telegram/initTelegram";
import type { StaffPermission } from "../types/staffAccess";

/** Backend UserRestaurantDto (camelCase) */
interface UserRestaurantDto {
  id: number;
  name: string;
  address: string;
  permissions: StaffPermission[];
}

function toAdminRestaurant(d: UserRestaurantDto): AdminRestaurant {
  return {
    id: d.id,
    name: d.name,
    address: d.address,
    permissions: d.permissions ?? [],
  };
}

/** Fetch restaurants for current staff user (my restaurants) */
export async function fetchMyRestaurants(userId: number): Promise<AdminRestaurant[]> {
  const resp = await fetch(`${BASE_URL}/users/${userId}/my-restaurants`, {
    headers: buildAdminApiJsonHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch my restaurants: ${resp.status}`);
  }
  const data = (await resp.json()) as UserRestaurantDto[];
  return data.map(toAdminRestaurant);
}
