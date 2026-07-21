import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  createDefaultSettings,
  loadAssets,
  loadSettings,
  saveAssets,
  saveSettings,
} from './storage';
import type { Asset, Settings } from './types';

const baseCurrencies = ['CHF', 'USD', 'EUR'];
const defaultSettings = createDefaultSettings(baseCurrencies[0]);

beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
  });
});

afterEach(() => vi.unstubAllGlobals());

describe('settings currency persistence', () => {
  it('uses the configured default for new, legacy, or unsupported settings', () => {
    expect(loadSettings(baseCurrencies)).toEqual(defaultSettings);
    localStorage.setItem('pesto_engine_settings', JSON.stringify({
      increment: 500,
      onlyBuy: true,
      optimalRedistribute: false,
      fractionalShares: false,
    }));
    expect(loadSettings(baseCurrencies).baseCurrency).toBe('CHF');
    localStorage.setItem('pesto_engine_settings', JSON.stringify({
      ...defaultSettings,
      baseCurrency: 'SEK',
    }));
    expect(loadSettings(baseCurrencies).baseCurrency).toBe('CHF');
    const settings: Settings = {
      ...defaultSettings,
      baseCurrency: 'USD',
    };
    saveSettings(settings);
    expect(loadSettings(baseCurrencies)).toEqual(settings);
  });
});

describe('asset currency persistence', () => {
  it('migrates legacy assets and round-trips quote currency', () => {
    localStorage.setItem('pesto_engine_assets', JSON.stringify([{
      id: 'a',
      ticker: 'VOO',
      provider: 'yahoo',
      desiredPercentage: 100,
      shares: 1,
      fees: 0,
      percentageFee: false,
    }]));

    expect(loadAssets()[0].currency).toBeNull();
    const assets: Asset[] = [{
      id: 'a',
      ticker: 'VWCE.DE',
      provider: 'yahoo',
      currency: 'EUR',
      desiredPercentage: 100,
      shares: 1,
      fees: 0,
      percentageFee: false,
    }];
    saveAssets(assets);
    expect(loadAssets()).toEqual(assets);
  });
});
