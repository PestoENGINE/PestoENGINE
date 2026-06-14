export interface Asset {
  id: string;
  ticker: string;
  provider: string | null;
  desiredPercentage: number;
  shares: number;
  fees: number;
  percentageFee: boolean;
}

export interface TickerResult {
  ticker: string;
  name: string;
  exchange: string;
  type: string;
  provider: string;
}

export interface Settings {
  increment: number;
  onlyBuy: boolean;
  optimalRedistribute: boolean;
  fractionalShares: boolean;
}

/** A single translatable message: a dictionary key plus optional params. */
export interface UiErrorItem {
  key: string;
  params?: Record<string, string | number>;
}

/**
 * A user-facing error that the logic modules emit without committing to a
 * language. `kind: 'key'` is one translated message; `kind: 'validation'` is a
 * list of them (mapped from a 422's structured `type`/`loc`); `kind: 'raw'`
 * carries an already-human passthrough message from the backend (which is
 * intentionally not translated).
 */
export type UiError =
  | { kind: 'key'; key: string; params?: Record<string, string | number> }
  | { kind: 'validation'; items: UiErrorItem[] }
  | { kind: 'raw'; text: string };

export interface AssetResultOut {
  id: number;
  ticker: string;
  current_percentage: number;
  desired_percentage: number;
  shares: number;
  allocated: number;
  ticker_price: number;
  fees: number;
  buy: number;
}

export interface RebalanceResponse {
  results: AssetResultOut[];
  total_fees: number;
  change: number;
}

export interface PortfolioExport {
  version: 1;
  exportedAt: string;
  settings: Settings;
  assets: Omit<Asset, 'id'>[];
}
