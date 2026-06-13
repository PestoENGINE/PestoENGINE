import { writable, derived, get } from 'svelte/store';
import en from './en.json';

// `en` is bundled as the synchronous fallback and the source of truth for the
// key set. Every other locale is its own dynamically-imported chunk, fetched
// only when selected, so the initial bundle stays flat as the community adds
// languages. Registering a language is a two-line change: add an `xx.json` and
// an entry in LOADERS + the Locale union. Anything untranslated falls back to
// English, so partial translations land incrementally.
export type Locale = 'en' | 'it';
export const LOCALES: readonly Locale[] = ['en', 'it'];
const STORAGE_KEY = 'pesto_engine_locale';

const LOADERS: Record<Locale, () => Promise<unknown>> = {
  en: () => Promise.resolve(en),
  it: () => import('./it.json').then((m) => m.default),
};

// Cache of loaded dictionaries (en is always present). `revision` is bumped
// whenever a newly fetched dictionary becomes available so `t` re-renders.
// `inflight` dedupes concurrent loads of the same locale (the locale
// subscription and the main.ts preload both request it at startup).
const dictionaries: Partial<Record<Locale, unknown>> = { en };
const inflight: Partial<Record<Locale, Promise<void>>> = {};
const revision = writable(0);

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

/**
 * Translate a key for a locale, falling back to English (always loaded) then to
 * the raw key. If the locale's dictionary has not loaded yet, the English
 * fallback is used until it arrives.
 */
export function translate(loc: Locale, key: string, params?: Record<string, string | number>): string {
  const raw = lookup(dictionaries[loc], key) ?? lookup(dictionaries.en, key) ?? key;
  return interpolate(raw, params);
}

/** Fetch and cache a locale's dictionary; concurrent calls share a single fetch. */
export function loadLocale(loc: Locale): Promise<void> {
  if (dictionaries[loc]) return Promise.resolve();
  return (inflight[loc] ??= LOADERS[loc]().then((dict) => {
    dictionaries[loc] = dict;
    revision.update((n) => n + 1);
  }));
}

export const locale = writable<Locale>(detectInitialLocale());

// Persist the choice, reflect it on <html lang>, and ensure its dictionary is
// fetched on every change (including the initial value).
locale.subscribe((value) => {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // ignore unavailable localStorage
  }
  if (typeof document !== 'undefined') document.documentElement.lang = value;
  void loadLocale(value);
});

export function setLocale(value: Locale): void {
  locale.set(value);
}

/** Reactive translator for markup: `{$t('settings.onlyBuy')}`. Re-renders as locales load. */
export const t = derived([locale, revision], ([$locale]) =>
  (key: string, params?: Record<string, string | number>) => translate($locale, key, params),
);

/** Non-reactive one-shot for imperative code (confirm(), document.title). */
export function tx(key: string, params?: Record<string, string | number>): string {
  return translate(get(locale), key, params);
}
