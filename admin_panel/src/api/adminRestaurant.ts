import { BASE_URL } from "./baseUrl";
import { buildAdminApiJsonHeaders, getTelegramInitData } from "../telegram/initTelegram";

export interface RestaurantDetail {
  id: number;
  name: string;
  address: string;
  imageLink: string | null;
  workingHoursFrom?: string | null;
  workingHoursTo?: string | null;
  ordersAcceptFrom?: string | null;
  ordersAcceptTo?: string | null;
  telegramGroupChatId?: number | null;
}

export async function fetchRestaurant(restaurantId: number): Promise<RestaurantDetail> {
  return fetch(`${BASE_URL}/restaurants/${restaurantId}`, {
    headers: buildAdminApiJsonHeaders(),
  }).then(async (r) => {
    if (!r.ok) throw new Error(String(r.status));
    return r.json() as Promise<RestaurantDetail>;
  });
}

export async function patchRestaurant(
  restaurantId: number,
  patch: Partial<
    Pick<
      RestaurantDetail,
      | "name"
      | "address"
      | "imageLink"
      | "workingHoursFrom"
      | "workingHoursTo"
      | "ordersAcceptFrom"
      | "ordersAcceptTo"
      | "telegramGroupChatId"
    >
  >
): Promise<RestaurantDetail> {
  const body: Record<string, string | number | null | undefined> = {};
  if (patch.name !== undefined) body.name = patch.name;
  if (patch.address !== undefined) body.address = patch.address;
  if (patch.imageLink !== undefined) body.imageLink = patch.imageLink;
  if (patch.workingHoursFrom !== undefined) body.workingHoursFrom = patch.workingHoursFrom;
  if (patch.workingHoursTo !== undefined) body.workingHoursTo = patch.workingHoursTo;
  if (patch.ordersAcceptFrom !== undefined) body.ordersAcceptFrom = patch.ordersAcceptFrom;
  if (patch.ordersAcceptTo !== undefined) body.ordersAcceptTo = patch.ordersAcceptTo;
  if (patch.telegramGroupChatId !== undefined) body.telegramGroupChatId = patch.telegramGroupChatId;
  const resp = await fetch(`${BASE_URL}/restaurants/${restaurantId}`, {
    method: "PATCH",
    headers: { ...buildAdminApiJsonHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`patch restaurant ${resp.status}`);
  return (await resp.json()) as RestaurantDetail;
}

export async function uploadRestaurantCover(restaurantId: number, file: File): Promise<string> {
  const init = getTelegramInitData();
  const fd = new FormData();
  fd.append("file", file);
  const headers: Record<string, string> = {};
  if (init) headers["X-Telegram-Init-Data"] = init;
  const resp = await fetch(
    `${BASE_URL}/restaurant-assets/upload?restaurantId=${restaurantId}`,
    { method: "POST", headers, body: fd }
  );
  if (!resp.ok) throw new Error(`upload ${resp.status}`);
  const j = (await resp.json()) as { path: string };
  return j.path;
}
