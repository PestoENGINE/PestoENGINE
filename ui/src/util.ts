// Shared, framework-agnostic helpers.

/** Parse the numeric value of an <input> event, defaulting to 0 on NaN. */
export function inputNumber(e: Event): number {
  return parseFloat((e.target as HTMLInputElement).value) || 0;
}

/** Mirrors the backend rule: round(total, 2) == 100.00 (app/schemas/request.py). */
export function percentagesSumTo100(sum: number): boolean {
  return Math.round(sum * 100) / 100 === 100;
}

/** Read the checked state of a checkbox <input> event. */
export function inputChecked(e: Event): boolean {
  return (e.target as HTMLInputElement).checked;
}

/**
 * Formats a buy quantity for display. Whole numbers render plainly ("5"),
 * fractional quantities up to 6 decimals with trailing zeros trimmed ("3.5").
 * Mirrors the backend's 6-dp fractional-share precision (app/schemas/result.py).
 */
export function formatShares(qty: number): string {
  if (Number.isInteger(qty)) return String(qty);
  return parseFloat(qty.toFixed(6)).toString();
}

/** RFC 4122 v4 id, using the platform crypto when available. */
export function uuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // randomUUID is gated to secure contexts; getRandomValues is not, so it still
  // gives crypto-grade randomness when the app is served over plain HTTP.
  const buf = new Uint8Array(16);
  crypto.getRandomValues(buf);
  buf[6] = (buf[6] & 0x0f) | 0x40; // version 4
  buf[8] = (buf[8] & 0x3f) | 0x80; // variant 10xx
  const hex = Array.from(buf, b => b.toString(16).padStart(2, '0'));
  return `${hex[0]}${hex[1]}${hex[2]}${hex[3]}-${hex[4]}${hex[5]}-${hex[6]}${hex[7]}-${hex[8]}${hex[9]}-${hex[10]}${hex[11]}${hex[12]}${hex[13]}${hex[14]}${hex[15]}`;
}
