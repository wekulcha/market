export const MARKET_STREETS = [
  'Новосередневский пр-т',
  'ул. Усадебный Парк',
  'ул. Золотошвейная',
  'ул. Братьев Бромлей',
] as const;

/** Разделитель частей адреса доставки. */
export const LOCATION_PARTS_SEP = ' · ';

export function parseLocationParts(address: string | null | undefined): {
  street: string;
  house: string;
  entrance: string;
  floor: string;
  apartment: string;
} {
  const raw = address?.trim() ?? '';
  if (!raw) return { street: MARKET_STREETS[0], house: '', entrance: '', floor: '', apartment: '' };
  const parts = raw.split(LOCATION_PARTS_SEP).map((s) => s.trim());
  if (parts.length >= 5) {
    return {
      street: parts[0] || MARKET_STREETS[0],
      house: parts[1] ?? '',
      entrance: parts[2] ?? '',
      floor: parts[3] ?? '',
      apartment: parts[4] ?? '',
    };
  }
  return { street: raw, house: '', entrance: '', floor: '', apartment: '' };
}

export function formatLocationParts(
  street: string,
  house: string,
  entrance: string,
  floor: string,
  apartment: string
): string {
  return [street, house, entrance, floor, apartment]
    .map((s) => s.trim())
    .filter(Boolean)
    .join(LOCATION_PARTS_SEP);
}

export function formatLocationShort(address: string | null | undefined): string {
  const { street, house, apartment } = parseLocationParts(address);
  return [street, house ? `д. ${house}` : '', apartment ? `кв. ${apartment}` : '']
    .map((value) => value.trim())
    .filter(Boolean)
    .join(', ');
}
