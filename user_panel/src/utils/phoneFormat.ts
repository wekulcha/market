export function isPlaceholderPhone(phone: string | null | undefined): boolean {
  return !phone || phone.trim().startsWith('tg-');
}

export function normalizePhoneInput(phone: string | null | undefined): string | null {
  if (!phone || !phone.trim() || isPlaceholderPhone(phone)) return null;

  const digits = phone.replace(/\D/g, '');
  if (digits.length === 10 && digits.startsWith('9')) {
    return `7${digits}`;
  }
  if (digits.length === 11 && digits.startsWith('8')) {
    return `7${digits.slice(1)}`;
  }
  if (digits.length < 6 || digits.length > 15) {
    return null;
  }
  return digits;
}

export function normalizeRussianPhoneInput(phone: string | null | undefined): string | null {
  if (!phone || !phone.trim() || isPlaceholderPhone(phone)) return null;
  const digits = phone.replace(/\D/g, '');
  if (digits.length === 10) return `7${digits}`;
  if (digits.length === 11 && digits.startsWith('7')) return digits;
  if (digits.length === 11 && digits.startsWith('8')) return `7${digits.slice(1)}`;
  return null;
}

export function phoneToRussianLocal10(phone: string | null | undefined): string {
  const normalized = normalizeRussianPhoneInput(phone);
  return normalized ? normalized.slice(1) : '';
}

export function russianLocal10ToStorage(local10: string): string | null {
  const digits = local10.replace(/\D/g, '').slice(0, 10);
  return digits.length === 10 ? `7${digits}` : null;
}

export function isRegisteredPhone(phone: string | null | undefined): boolean {
  return normalizePhoneInput(phone) !== null;
}

export function isRussianPhone(phone: string | null | undefined): boolean {
  return normalizeRussianPhoneInput(phone) !== null;
}

export function phoneToInputValue(phone: string | null | undefined): string {
  if (isPlaceholderPhone(phone)) return '';
  const normalized = normalizePhoneInput(phone);
  return normalized ? `+${normalized}` : phone?.trim() ?? '';
}

export function displayPhone(phone: string | null | undefined): string {
  const input = phoneToInputValue(phone);
  return input || '—';
}
