export function normalizeBaseCurrency(
  value: unknown,
  supportedCurrencies: readonly string[],
): string | null {
  const normalized = normalizeQuoteCurrency(value);
  return normalized !== null && supportedCurrencies.includes(normalized)
    ? normalized
    : null;
}

/** Normalize a provider quote currency without restricting it to base currencies. */
export function normalizeQuoteCurrency(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const raw = value.trim();
  const normalized = raw === 'GBp' ? 'GBX' : raw.toUpperCase();
  return /^[A-Z]{3}$/.test(normalized) ? normalized : null;
}
