import { describe, it, expect } from 'vitest';
import { parsePortfolio, buildExport } from './portfolio-io';
import type { Asset, Settings } from './types';

function fileWith(overrides: Record<string, unknown> = {}): string {
  return JSON.stringify({
    version: 1,
    exportedAt: '2026-05-25T10:00:00Z',
    settings: { increment: 1000, onlyBuy: true, optimalRedistribute: false },
    assets: [
      { ticker: 'VOO', provider: null, desiredPercentage: 60, shares: 10, fees: 0.5, percentageFee: true },
      { ticker: 'BND', provider: null, desiredPercentage: 40, shares: 5, fees: 0, percentageFee: false },
    ],
    ...overrides,
  });
}

describe('parsePortfolio', () => {
  it('accepts a valid v1 file and assigns fresh unique ids', () => {
    const r = parsePortfolio(fileWith());
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.settings).toEqual({ increment: 1000, onlyBuy: true, optimalRedistribute: false });
    expect(r.assets).toHaveLength(2);
    expect(r.assets[0]).toMatchObject({ ticker: 'VOO', desiredPercentage: 60, shares: 10, fees: 0.5, percentageFee: true });
    expect(typeof r.assets[0].id).toBe('string');
    expect(r.assets[0].id).not.toBe('');
    expect(r.assets[0].id).not.toBe(r.assets[1].id);
    expect(r.sumWarning).toBe(false);
  });

  it('defaults onlyBuy/optimalRedistribute when missing', () => {
    const r = parsePortfolio(fileWith({ settings: { increment: 500 } }));
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.settings).toEqual({ increment: 500, onlyBuy: true, optimalRedistribute: false });
  });

  it('flags sumWarning when targets do not sum to 100', () => {
    const r = parsePortfolio(fileWith({
      assets: [{ ticker: 'VOO', provider: null, desiredPercentage: 30, shares: 0, fees: 0, percentageFee: false }],
    }));
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.sumWarning).toBe(true);
  });

  it('rejects non-JSON input', () => {
    expect(parsePortfolio('{nope')).toEqual({ ok: false, error: 'File is not valid JSON.' });
  });

  it('rejects a non-object payload', () => {
    expect(parsePortfolio('42')).toEqual({ ok: false, error: 'Invalid portfolio file.' });
  });

  it('rejects an unsupported version', () => {
    expect(parsePortfolio(fileWith({ version: 2 }))).toEqual({
      ok: false, error: 'Unsupported export version. Expected version 1.',
    });
  });

  it('rejects missing settings', () => {
    expect(parsePortfolio(fileWith({ settings: null }))).toEqual({
      ok: false, error: 'Invalid portfolio file: missing settings.',
    });
  });

  it('rejects an empty assets array', () => {
    expect(parsePortfolio(fileWith({ assets: [] }))).toEqual({
      ok: false, error: 'Invalid portfolio file: assets must be a non-empty array.',
    });
  });

  it('rejects an invalid increment', () => {
    expect(parsePortfolio(fileWith({ settings: { increment: -1 } }))).toEqual({
      ok: false, error: 'Invalid portfolio file: invalid increment.',
    });
  });

  it('reports the offending asset index for a missing ticker', () => {
    const r = parsePortfolio(fileWith({
      assets: [
        { ticker: 'VOO', provider: null, desiredPercentage: 50, shares: 0, fees: 0, percentageFee: false },
        { ticker: 123, provider: null, desiredPercentage: 50, shares: 0, fees: 0, percentageFee: false },
      ],
    }));
    expect(r).toEqual({ ok: false, error: 'Invalid portfolio file: asset 2 missing ticker.' });
  });

  it('rejects negative shares', () => {
    const r = parsePortfolio(fileWith({
      assets: [{ ticker: 'VOO', provider: null, desiredPercentage: 100, shares: -3, fees: 0, percentageFee: false }],
    }));
    expect(r).toEqual({ ok: false, error: 'Invalid portfolio file: asset 1 invalid shares.' });
  });

  it('rejects a non-boolean percentageFee', () => {
    const r = parsePortfolio(fileWith({
      assets: [{ ticker: 'VOO', provider: null, desiredPercentage: 100, shares: 0, fees: 0, percentageFee: 'yes' }],
    }));
    expect(r).toEqual({ ok: false, error: 'Invalid portfolio file: asset 1 invalid percentageFee.' });
  });
});

describe('buildExport / round-trip', () => {
  const settings: Settings = { increment: 250, onlyBuy: false, optimalRedistribute: true };
  const assets: Asset[] = [
    { id: 'local-1', ticker: 'VWCE', provider: 'yahoo', desiredPercentage: 70, shares: 12, fees: 1, percentageFee: false },
    { id: 'local-2', ticker: 'AGGH', provider: null, desiredPercentage: 30, shares: 3, fees: 0, percentageFee: true },
  ];

  it('strips local ids and stamps version 1', () => {
    const out = buildExport(settings, assets);
    expect(out.version).toBe(1);
    expect(out.settings).toEqual(settings);
    expect(out.assets).toHaveLength(2);
    expect(out.assets[0]).not.toHaveProperty('id');
    expect(typeof out.exportedAt).toBe('string');
  });

  it('survives a buildExport -> parsePortfolio round-trip', () => {
    const r = parsePortfolio(JSON.stringify(buildExport(settings, assets)));
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.settings).toEqual(settings);
    expect(r.assets.map(({ id: _id, ...rest }) => rest)).toEqual(
      assets.map(({ id: _id, ...rest }) => rest),
    );
  });
});
