import type { Asset, Settings } from './types';

const KEYS = {
  settings: 'pesto_engine_settings',
  assets: 'pesto_engine_assets',
  darkMode: 'pesto_engine_dark_mode',
} as const;

export const DEFAULT_SETTINGS: Settings = {
  increment: 1000,
  onlyBuy: true,
  optimalRedistribute: false,
};

function tryParse<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function loadSettings(): Settings {
  return { ...DEFAULT_SETTINGS, ...tryParse<Partial<Settings>>(KEYS.settings, {}) };
}

function isValidAsset(a: unknown): a is Asset {
  if (typeof a !== 'object' || a === null) return false;
  const obj = a as Record<string, unknown>;
  return (
    typeof obj.id === 'string' &&
    typeof obj.ticker === 'string' &&
    typeof obj.desiredPercentage === 'number' &&
    typeof obj.shares === 'number' &&
    typeof obj.fees === 'number' &&
    typeof obj.percentageFee === 'boolean'
  );
}

export function loadAssets(): Asset[] {
  const val = tryParse<unknown>(KEYS.assets, null);
  if (!Array.isArray(val)) return [];
  if (!val.every(isValidAsset)) {
    console.warn('Stored assets failed validation, resetting to empty.');
    return [];
  }
  return val;
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
