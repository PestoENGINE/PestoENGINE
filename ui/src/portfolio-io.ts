import type { Settings, Asset, PortfolioExport } from './types';
import { DEFAULT_SETTINGS } from './storage';
import { percentagesSumTo100, uuid } from './util';

export type ImportResult =
  | { ok: true; settings: Settings; assets: Asset[]; sumWarning: boolean }
  | { ok: false; error: string };

/**
 * Validates and parses a portfolio export file. Pure: no confirm, no DOM, no
 * state mutation. On success, fresh ids are assigned to each imported asset and
 * `sumWarning` flags target percentages that do not add up to 100. The caller
 * decides whether to confirm and apply.
 */
export function parsePortfolio(text: string): ImportResult {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return { ok: false, error: 'File is not valid JSON.' };
  }

  if (typeof data !== 'object' || data === null) return { ok: false, error: 'Invalid portfolio file.' };
  const d = data as Record<string, unknown>;

  if (d.version !== 1) return { ok: false, error: 'Unsupported export version. Expected version 1.' };
  if (typeof d.settings !== 'object' || d.settings === null) return { ok: false, error: 'Invalid portfolio file: missing settings.' };
  if (!Array.isArray(d.assets) || d.assets.length === 0) return { ok: false, error: 'Invalid portfolio file: assets must be a non-empty array.' };

  const s = d.settings as Record<string, unknown>;
  if (typeof s.increment !== 'number' || s.increment < 0) return { ok: false, error: 'Invalid portfolio file: invalid increment.' };

  for (let i = 0; i < d.assets.length; i++) {
    const a = d.assets[i] as Record<string, unknown>;
    if (typeof a.ticker !== 'string' || !a.ticker) return { ok: false, error: `Invalid portfolio file: asset ${i + 1} missing ticker.` };
    if (typeof a.desiredPercentage !== 'number' || a.desiredPercentage < 0) return { ok: false, error: `Invalid portfolio file: asset ${i + 1} invalid desiredPercentage.` };
    if (typeof a.shares !== 'number' || a.shares < 0) return { ok: false, error: `Invalid portfolio file: asset ${i + 1} invalid shares.` };
    if (typeof a.fees !== 'number' || a.fees < 0) return { ok: false, error: `Invalid portfolio file: asset ${i + 1} invalid fees.` };
    if (typeof a.percentageFee !== 'boolean') return { ok: false, error: `Invalid portfolio file: asset ${i + 1} invalid percentageFee.` };
  }

  const sum = (d.assets as Array<{ desiredPercentage: number }>).reduce((acc, a) => acc + a.desiredPercentage, 0);
  const sumWarning = !percentagesSumTo100(sum);

  const settings: Settings = {
    increment: s.increment as number,
    onlyBuy: typeof s.onlyBuy === 'boolean' ? s.onlyBuy : DEFAULT_SETTINGS.onlyBuy,
    optimalRedistribute: typeof s.optimalRedistribute === 'boolean' ? s.optimalRedistribute : DEFAULT_SETTINGS.optimalRedistribute,
    fractionalShares: typeof s.fractionalShares === 'boolean' ? s.fractionalShares : DEFAULT_SETTINGS.fractionalShares,
  };

  const assets: Asset[] = (d.assets as Array<Record<string, unknown>>).map(a => ({
    id: uuid(),
    ticker: a.ticker as string,
    provider: typeof a.provider === 'string' ? a.provider : null,
    desiredPercentage: a.desiredPercentage as number,
    shares: a.shares as number,
    fees: a.fees as number,
    percentageFee: a.percentageFee as boolean,
  }));

  return { ok: true, settings, assets, sumWarning };
}

/** Builds the versioned export payload (assets stripped of their local id). */
export function buildExport(settings: Settings, assets: Asset[]): PortfolioExport {
  return {
    version: 1,
    exportedAt: new Date().toISOString(),
    settings,
    assets: assets.map(({ id: _id, ...rest }) => rest),
  };
}
