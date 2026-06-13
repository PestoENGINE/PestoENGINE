import { describe, it, expect, afterEach } from 'vitest';
import { get } from 'svelte/store';
import {
  resolveLocale, lookup, interpolate, translate, loadLocale, t, locale, setLocale,
} from './index';
import enDict from './en.json';
import itDict from './it.json';

afterEach(() => setLocale('en'));

describe('resolveLocale', () => {
  it('honours a valid stored locale', () => {
    expect(resolveLocale('it', 'en-US')).toBe('it');
    expect(resolveLocale('en', 'it-IT')).toBe('en');
  });

  it('falls back to the navigator language when nothing is stored', () => {
    expect(resolveLocale(null, 'it-IT')).toBe('it');
    expect(resolveLocale(null, 'en-GB')).toBe('en');
  });

  it('ignores an unrecognised stored value', () => {
    expect(resolveLocale('de', 'it')).toBe('it');
  });

  it('defaults to en when nothing is known', () => {
    expect(resolveLocale(null, undefined)).toBe('en');
  });
});

describe('lookup', () => {
  it('resolves a dot path to a string', () => {
    expect(lookup({ a: { b: 'x' } }, 'a.b')).toBe('x');
  });

  it('returns undefined for a missing path', () => {
    expect(lookup({ a: {} }, 'a.b')).toBeUndefined();
  });

  it('returns undefined when the path resolves to a non-string', () => {
    expect(lookup({ a: { b: {} } }, 'a.b')).toBeUndefined();
  });
});

describe('interpolate', () => {
  it('replaces named params', () => {
    expect(interpolate('hi {name}', { name: 'Bo' })).toBe('hi Bo');
  });

  it('stringifies numeric params', () => {
    expect(interpolate('in {n} s', { n: 30 })).toBe('in 30 s');
  });

  it('leaves an unknown placeholder untouched', () => {
    expect(interpolate('hi {name}', {})).toBe('hi {name}');
  });

  it('returns the raw string when no params are given', () => {
    expect(interpolate('plain')).toBe('plain');
  });
});

describe('translate', () => {
  // English is bundled, so it resolves synchronously and is the fallback.
  it('returns the English string synchronously', () => {
    expect(translate('en', 'settings.onlyBuy')).toBe('Only buy');
  });

  // This must run before any test loads the it dictionary (lazy cache is shared
  // across the module). It documents the pre-load fallback to English.
  it('falls back to English for a lazily-loaded locale that is not loaded yet', () => {
    expect(translate('it', 'settings.onlyBuy')).toBe('Only buy');
  });

  it('returns the locale string once its dictionary is loaded', async () => {
    await loadLocale('it');
    expect(translate('it', 'settings.onlyBuy')).toBe('Solo acquisti');
  });

  it('interpolates params', () => {
    expect(translate('en', 'errors.tooManyRequestsRetry', { n: 30 }))
      .toBe('Too many requests. Try again in 30 seconds.');
  });

  it('falls back to the raw key when the key is missing entirely', () => {
    expect(translate('en', 'nope.nope')).toBe('nope.nope');
  });
});

describe('t store / setLocale', () => {
  it('reflects the active locale reactively once loaded', async () => {
    await loadLocale('it');
    setLocale('it');
    expect(get(t)('results.title')).toBe('Risultato');
    setLocale('en');
    expect(get(t)('results.title')).toBe('Result');
  });

  it('updates the locale store', () => {
    setLocale('it');
    expect(get(locale)).toBe('it');
  });
});

describe('en/it key parity', () => {
  function paths(obj: unknown, prefix = ''): string[] {
    if (typeof obj !== 'object' || obj === null) return [prefix];
    return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
      paths(v, prefix ? `${prefix}.${k}` : k),
    );
  }

  it('it.json defines exactly the same keys as en.json', () => {
    expect(new Set(paths(itDict))).toEqual(new Set(paths(enDict)));
  });
});
