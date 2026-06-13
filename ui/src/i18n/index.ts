import { writable, derived, get } from 'svelte/store';
import en from './en.json';
import it from './it.json';

// Adding a language is a two-line change: drop an `xx.json` next to these and
// register it in DICTIONARIES + the Locale union below. Missing keys in a
// partial translation fall back to English, so contributions can land
// incrementally. English is the source of truth for the key set.
export type Locale = 'en' | 'it';
export const LOCALES: readonly Locale[] = ['en', 'it'];
const DICTIONARIES: Record<Locale, unknown> = { en, it };
const STORAGE_KEY = 'pesto_engine_locale';

/** Pure locale decision: a valid stored choice wins, else the browser language, else English. */
export function resolveLocale(stored: string | null, navLang: string | undefined): Locale {
  if (stored === 'en' || stored === 'it') return stored;
  return (navLang ?? '').toLowerCase().startsWith('it') ? 'it' : 'en';
}

function detectInitialLocale(): Locale {
  let stored: string | null = null;
  try {
    stored = localStorage.getItem(STORAGE_KEY);
  } catch {
    // localStorage may be unavailable (private mode, SSR, tests)
  }
  const navLang = typeof navigator !== 'undefined' ? navigator.language : undefined;
  return resolveLocale(stored, navLang);
}

/** Resolve a dot-separated path against a dictionary, returning a string or undefined. */
export function lookup(dict: unknown, key: string): string | undefined {
  const value = key.split('.').reduce<unknown>(
    (acc, part) => (acc && typeof acc === 'object' ? (acc as Record<string, unknown>)[part] : undefined),
    dict,
  );
  return typeof value === 'string' ? value : undefined;
}

/** Replace `{name}` placeholders; unknown placeholders are left verbatim. */
export function interpolate(raw: string, params?: Record<string, string | number>): string {
  if (!params) return raw;
  return raw.replace(/\{(\w+)\}/g, (_match, name: string) =>
    name in params ? String(params[name]) : `{${name}}`,
  );
}

/** Translate a key for a locale, falling back to English then to the raw key. */
export function translate(loc: Locale, key: string, params?: Record<string, string | number>): string {
  const raw = lookup(DICTIONARIES[loc], key) ?? lookup(DICTIONARIES.en, key) ?? key;
  return interpolate(raw, params);
}

export const locale = writable<Locale>(detectInitialLocale());

// Persist the choice and reflect it on <html lang> on every change.
locale.subscribe((value) => {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // ignore unavailable localStorage
  }
  if (typeof document !== 'undefined') document.documentElement.lang = value;
});

export function setLocale(value: Locale): void {
  locale.set(value);
}

/** Reactive translator for markup: `{$t('settings.onlyBuy')}`. */
export const t = derived(locale, ($locale) =>
  (key: string, params?: Record<string, string | number>) => translate($locale, key, params),
);

/** Non-reactive one-shot for imperative code (confirm(), document.title). */
export function tx(key: string, params?: Record<string, string | number>): string {
  return translate(get(locale), key, params);
}
