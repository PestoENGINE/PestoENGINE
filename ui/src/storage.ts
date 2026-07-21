import type { Asset, Settings } from './types';
import { normalizeBaseCurrency, normalizeQuoteCurrency } from './currency';

const KEYS = {
  settings: 'pesto_engine_settings',
  assets: 'pesto_engine_assets',
  darkMode: 'pesto_engine_dark_mode',
} as const;

export function createDefaultSettings(baseCurrency: string): Settings {
  return {
    increment: 1000,
    baseCurrency,
    onlyBuy: true,
    optimalRedistribute: false,
    fractionalShares: false,
  };
}

function tryParse<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function loadSettings(baseCurrencies: readonly string[]): Settings {
  const defaultCurrency = baseCurrencies[0];
  const defaults = createDefaultSettings(defaultCurrency);
  const stored = tryParse<Partial<Settings> | null>(KEYS.settings, null);
  if (stored === null) return defaults;
  const baseCurrency =
    normalizeBaseCurrency(
      stored.baseCurrency,
      baseCurrencies,
    ) ?? defaultCurrency;
  return {
    ...defaults,
    ...stored,
    baseCurrency,
  };
}

type StoredAsset = Omit<Asset, 'provider' | 'currency'> & {
  provider?: string | null;
  currency?: string | null;
};

function isValidAsset(a: unknown): a is StoredAsset {
  if (typeof a !== 'object' || a === null) return false;
  const obj = a as Record<string, unknown>;
  return (
    typeof obj.id === 'string' &&
    typeof obj.ticker === 'string' &&
    typeof obj.desiredPercentage === 'number' &&
    typeof obj.shares === 'number' &&
    typeof obj.fees === 'number' &&
    typeof obj.percentageFee === 'boolean' &&
    // provider is optional for backward compat with pre-feature localStorage entries
    (obj.provider === undefined || obj.provider === null || typeof obj.provider === 'string')
  );
}

export function loadAssets(): Asset[] {
  const val = tryParse<unknown>(KEYS.assets, null);
  if (!Array.isArray(val)) return [];
  if (!val.every(isValidAsset)) {
    console.warn('Stored assets failed validation, resetting to empty.');
    return [];
  }
  return val.map(a => ({
    ...a,
    provider: a.provider ?? null,
    currency: normalizeQuoteCurrency(a.currency),
  }));
}

export function saveSettings(s: Settings): void {
  localStorage.setItem(KEYS.settings, JSON.stringify(s));
}

export function saveAssets(a: Asset[]): void {
  localStorage.setItem(KEYS.assets, JSON.stringify(a));
}

export function loadDarkMode(): boolean {
  return tryParse<boolean>(KEYS.darkMode, false);
}

export function saveDarkMode(v: boolean): void {
  localStorage.setItem(KEYS.darkMode, JSON.stringify(v));
}
