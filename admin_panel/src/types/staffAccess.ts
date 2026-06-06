export type StaffPermission = "CAN_EDIT_MENU" | "CAN_LOOK_ORDERS";

export const FULL_ACCESS_PERMISSION: StaffPermission = "CAN_EDIT_MENU";
export const LIMITED_ACCESS_PERMISSION: StaffPermission = "CAN_LOOK_ORDERS";

export const STAFF_PERMISSION_LABELS: Record<StaffPermission, string> = {
  CAN_EDIT_MENU: "Полный доступ",
  CAN_LOOK_ORDERS: "Ограниченный доступ",
};

export function hasFullRestaurantAccess(
  permissions: readonly string[] | null | undefined
): boolean {
  return Array.isArray(permissions) && permissions.includes(FULL_ACCESS_PERMISSION);
}
