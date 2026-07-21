import type { Asset, Settings, RebalanceResponse, TickerResult, UiError, UiErrorItem } from './types';

/** Load and validate the backend-owned runtime configuration. */
export async function loadBaseCurrencies(
  fetchFn: typeof fetch = fetch,
): Promise<string[]> {
  const res = await fetchFn('/v1/config');
  if (!res.ok) throw new Error(`Configuration request failed with ${res.status}`);

  const { base_currencies: baseCurrencies } = await res.json() as {
    base_currencies?: string[];
  };
  if (!Array.isArray(baseCurrencies) || baseCurrencies.length === 0) {
    throw new Error('Invalid supported base currencies');
  }
  return baseCurrencies;
}

interface RebalanceBody {
  only_buy: boolean;
  increment: number;
  base_currency: string;
  optimal_redistribute: boolean;
  fractional_shares: boolean;
  assets: Array<{
    ticker: string;
    provider: string | null;
    currency: string | null;
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
    base_currency: settings.baseCurrency,
    optimal_redistribute: settings.optimalRedistribute,
    fractional_shares: settings.fractionalShares,
    assets: assets.map(a => ({
      ticker: a.ticker,
      provider: a.provider ?? null,
      currency: a.currency,
      desired_percentage: a.desiredPercentage,
      shares: a.shares,
      fees: a.fees,
      percentage_fee: a.percentageFee,
    })),
  };
}

/** One item of FastAPI's 422 `detail` array (Pydantic validation error). */
interface PydanticError {
  type?: string;
  loc?: (string | number)[];
  msg?: string;
  ctx?: Record<string, unknown>;
}

/**
 * Maps one Pydantic 422 error to a translatable item. Standard field
 * constraints are routed by (type, field); custom validation rules carry
 * stable codes. Anything
 * unmapped falls back to the generic key wrapping the backend's English `msg`.
 */
function mapValidationError(d: PydanticError): UiErrorItem {
  const type = d.type ?? '';
  const loc = d.loc ?? [];
  const ctx = d.ctx ?? {};
  const ai = loc.indexOf('assets');
  const assetIndex = ai >= 0 && typeof loc[ai + 1] === 'number' ? (loc[ai + 1] as number) : null;
  const names = loc.filter((x): x is string => typeof x === 'string' && x !== 'body');
  const field = names.length ? names[names.length - 1] : null;

  switch (type) {
    case 'percentage_sum':
      return { key: 'errors.invalid.percentageSum', params: { total: Number(ctx.total) } };
    case 'percentage_fee_cap':
      if (assetIndex !== null) return { key: 'errors.invalid.feeCap', params: { n: assetIndex + 1 } };
      break;
    case 'greater_than_equal':
    case 'less_than_equal':
      if (field === 'desired_percentage') return { key: 'errors.invalid.percentageRange' };
      if (field === 'shares') return { key: 'errors.invalid.sharesNegative' };
      if (field === 'fees') return { key: 'errors.invalid.feeNegative' };
      if (field === 'increment') return { key: 'errors.invalid.incrementNegative' };
      break;
    case 'string_too_short':
      if (field === 'ticker') return { key: 'errors.invalid.tickerRequired' };
      break;
    case 'too_short':
      if (field === 'assets') return { key: 'errors.invalid.assetsRequired' };
      break;
  }
  return { key: 'errors.validation', params: { detail: d.msg || type || 'invalid' } };
}

/** Drops items that translate to the same key+params (e.g. two assets out of range). */
function dedupeItems(items: UiErrorItem[]): UiErrorItem[] {
  const seen = new Set<string>();
  return items.filter((it) => {
    const id = `${it.key}:${JSON.stringify(it.params ?? {})}`;
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

/**
 * Maps a non-ok rebalance Response to a language-agnostic UiError, so the
 * component owns all translation. 422 validation errors are mapped from their
 * stable Pydantic `type`/`loc` to dictionary keys; 429 prefers the translated
 * key (with seconds from `Retry-After`) and only passes prose through raw when
 * an upstream limiter omits the header; 502 shows a generic translated message.
 * May reject if a 422 body is not valid JSON; callers treat that like a network
 * failure, matching the original inline behavior.
 */
export async function rebalanceError(res: Response): Promise<UiError> {
  if (res.status === 422) {
    const data = await res.json();
    if (Array.isArray(data.detail)) {
      return { kind: 'validation', items: dedupeItems((data.detail as PydanticError[]).map(mapValidationError)) };
    }
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    return { kind: 'key', key: 'errors.validation', params: { detail } };
  }
  if (res.status === 429) {
    const retryAfter = res.headers.get('retry-after');
    if (retryAfter) return { kind: 'key', key: 'errors.tooManyRequestsRetry', params: { n: retryAfter } };
    const data = await res.json().catch(() => ({}));
    if (typeof data.detail === 'string') return { kind: 'raw', text: data.detail };
    return { kind: 'key', key: 'errors.tooManyRequests' };
  }
  if (res.status === 502) {
    return { kind: 'key', key: 'errors.marketData' };
  }
  return { kind: 'key', key: 'errors.requestFailedRetry' };
}

type RebalanceOutcome =
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

type TickerSearchOutcome =
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
