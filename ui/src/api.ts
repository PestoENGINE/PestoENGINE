import type { Asset, Settings, RebalanceResponse, TickerResult, UiError } from './types';

export interface RebalanceBody {
  only_buy: boolean;
  increment: number;
  optimal_redistribute: boolean;
  fractional_shares: boolean;
  assets: Array<{
    ticker: string;
    provider: string | null;
    desired_percentage: number;
    shares: number;
    fees: number;
    percentage_fee: boolean;
  }>;
}

/** Maps the camelCase UI model to the snake_case backend payload. */
export function buildRebalanceBody(settings: Settings, assets: Asset[]): RebalanceBody {
  return {
    only_buy: settings.onlyBuy,
    increment: settings.increment,
    optimal_redistribute: settings.optimalRedistribute,
    fractional_shares: settings.fractionalShares,
    assets: assets.map(a => ({
      ticker: a.ticker,
      provider: a.provider ?? null,
      desired_percentage: a.desiredPercentage,
      shares: a.shares,
      fees: a.fees,
      percentage_fee: a.percentageFee,
    })),
  };
}

/**
 * Maps a non-ok rebalance Response to a language-agnostic UiError.
 * `kind: 'key'` is translated in the component; `kind: 'raw'` is a passthrough
 * of the backend's own message (not translated). May reject if a 422 body is
 * not valid JSON; callers treat that like a network failure, matching the
 * original inline behavior.
 */
export async function rebalanceError(res: Response): Promise<UiError> {
  if (res.status === 422) {
    const data = await res.json();
    const detail = Array.isArray(data.detail)
      ? data.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ')
      : typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    return { kind: 'key', key: 'errors.validation', params: { detail } };
  }
  if (res.status === 429) {
    const data = await res.json().catch(() => ({}));
    if (typeof data.detail === 'string') return { kind: 'raw', text: data.detail };
    const retryAfter = res.headers.get('retry-after');
    return retryAfter
      ? { kind: 'key', key: 'errors.tooManyRequestsRetry', params: { n: retryAfter } }
      : { kind: 'key', key: 'errors.tooManyRequests' };
  }
  if (res.status === 502) {
    const data = await res.json().catch(() => ({}));
    return typeof data.detail === 'string'
      ? { kind: 'raw', text: data.detail }
      : { kind: 'key', key: 'errors.marketData' };
  }
  return { kind: 'key', key: 'errors.requestFailedRetry' };
}

export type RebalanceOutcome =
  | { ok: true; data: RebalanceResponse }
  | { ok: false; error: UiError };

/**
 * Sends the rebalance request and returns a discriminated outcome.
 * A network failure (fetch rejecting) propagates to the caller; HTTP error
 * statuses are mapped to a message. `fetchFn` is injectable for tests.
 */
export async function runRebalance(
  settings: Settings,
  assets: Asset[],
  fetchFn: typeof fetch = fetch,
): Promise<RebalanceOutcome> {
  const res = await fetchFn('/v1/rebalance', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buildRebalanceBody(settings, assets)),
  });
  if (res.ok) {
    return { ok: true, data: await res.json() as RebalanceResponse };
  }
  return { ok: false, error: await rebalanceError(res) };
}

export type TickerSearchOutcome =
  | { ok: true; results: TickerResult[] }
  | { ok: false; rateLimited: boolean };

/**
 * Searches tickers for the autocomplete. Returns a discriminated outcome:
 * results on success, or a flag distinguishing rate-limiting (429) from any
 * other non-ok status. A network failure propagates so the caller can keep the
 * field manually editable. `fetchFn` is injectable for tests.
 */
export async function searchTickers(
  q: string,
  fetchFn: typeof fetch = fetch,
): Promise<TickerSearchOutcome> {
  const res = await fetchFn(`/v1/tickers/search?q=${encodeURIComponent(q)}`);
  if (res.status === 429) return { ok: false, rateLimited: true };
  if (!res.ok) return { ok: false, rateLimited: false };
  const data = await res.json();
  return { ok: true, results: data.results ?? [] };
}
