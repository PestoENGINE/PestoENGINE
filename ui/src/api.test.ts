import { describe, it, expect } from 'vitest';
import { buildRebalanceBody, loadConfig, rebalanceError, runRebalance, runRebalanceInBrowser, searchTickers } from './api';
import type { Asset, Settings, RebalanceResponse } from './types';

const settings: Settings = {
  increment: 1000,
  baseCurrency: 'USD',
  onlyBuy: true,
  optimalRedistribute: false,
  fractionalShares: false,
};
const assets: Asset[] = [
  { id: 'a1', ticker: 'VOO', provider: 'yahoo', currency: 'USD', desiredPercentage: 60, shares: 10, fees: 0.5, percentageFee: true },
];

function jsonResponse(body: unknown, init: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'content-type': 'application/json' },
    ...init,
  });
}

describe('loadConfig', () => {
  it('maps the backend runtime currency contract', async () => {
    const fetchFn = async () => jsonResponse({
      base_currencies: ['CHF', 'USD', 'EUR'],
      rebalance_engine: 'frontend',
    }, { status: 200 });

    await expect(loadConfig(fetchFn as typeof fetch))
      .resolves.toEqual({ baseCurrencies: ['CHF', 'USD', 'EUR'], rebalanceEngine: 'frontend' });
  });

  it('computes on the backend unless the browser engine is selected', async () => {
    for (const engine of [undefined, 'backend', 'something-else']) {
      const fetchFn = async () => jsonResponse({ base_currencies: ['EUR'], rebalance_engine: engine }, { status: 200 });
      expect((await loadConfig(fetchFn as typeof fetch)).rebalanceEngine).toBe('backend');
    }
  });

  it('rejects an invalid or unavailable runtime currency contract', async () => {
    const invalid = async () => jsonResponse({
      base_currencies: [],
    }, { status: 200 });
    const unavailable = async () => jsonResponse({}, { status: 503 });

    await expect(loadConfig(invalid as typeof fetch))
      .rejects.toThrow('Invalid supported base currencies');
    await expect(loadConfig(unavailable as typeof fetch))
      .rejects.toThrow('Configuration request failed with 503');
  });
});

describe('buildRebalanceBody', () => {
  it('maps camelCase settings/assets to snake_case', () => {
    expect(buildRebalanceBody(settings, assets)).toEqual({
      only_buy: true,
      increment: 1000,
      base_currency: 'USD',
      optimal_redistribute: false,
      fractional_shares: false,
      assets: [
        { ticker: 'VOO', provider: 'yahoo', currency: 'USD', desired_percentage: 60, shares: 10, fees: 0.5, percentage_fee: true },
      ],
    });
  });

  it('defaults a missing provider to null', () => {
    const body = buildRebalanceBody(settings, [{ ...assets[0], provider: null, currency: null }]);
    expect(body.assets[0].provider).toBeNull();
    expect(body.assets[0].currency).toBeNull();
  });
});

describe('rebalanceError', () => {
  it('maps a 422 array detail to translatable validation items', async () => {
    const res = jsonResponse({ detail: [
      { type: 'percentage_sum', loc: ['body'], ctx: { total: 90 }, msg: 'must sum to 100' },
      { type: 'greater_than_equal', loc: ['body', 'assets', 0, 'shares'], ctx: { ge: 0 }, msg: '>= 0' },
    ] }, { status: 422 });
    expect(await rebalanceError(res)).toEqual({
      kind: 'validation',
      items: [
        { key: 'errors.invalid.percentageSum', params: { total: 90 } },
        { key: 'errors.invalid.sharesNegative' },
      ],
    });
  });

  it('routes percentage-range and fee-cap errors, fee-cap with the asset index', async () => {
    const res = jsonResponse({ detail: [
      { type: 'less_than_equal', loc: ['body', 'assets', 2, 'desired_percentage'], ctx: { le: 100 } },
      { type: 'percentage_fee_cap', loc: ['body', 'assets', 1], ctx: { fees: 150 } },
    ] }, { status: 422 });
    expect(await rebalanceError(res)).toEqual({
      kind: 'validation',
      items: [
        { key: 'errors.invalid.percentageRange' },
        { key: 'errors.invalid.feeCap', params: { n: 2 } },
      ],
    });
  });

  it('falls back to the generic key for an unmapped 422 type', async () => {
    const res = jsonResponse({ detail: [{ type: 'whatever', loc: ['body', 'x'], msg: 'odd' }] }, { status: 422 });
    expect(await rebalanceError(res)).toEqual({
      kind: 'validation',
      items: [{ key: 'errors.validation', params: { detail: 'odd' } }],
    });
  });

  it('de-duplicates identical validation items', async () => {
    const res = jsonResponse({ detail: [
      { type: 'less_than_equal', loc: ['body', 'assets', 0, 'desired_percentage'] },
      { type: 'greater_than_equal', loc: ['body', 'assets', 1, 'desired_percentage'] },
    ] }, { status: 422 });
    expect(await rebalanceError(res)).toEqual({
      kind: 'validation',
      items: [{ key: 'errors.invalid.percentageRange' }],
    });
  });

  it('passes a 422 string detail through the validation key', async () => {
    const res = jsonResponse({ detail: 'bad input' }, { status: 422 });
    expect(await rebalanceError(res)).toEqual({ kind: 'key', key: 'errors.validation', params: { detail: 'bad input' } });
  });

  it('uses the retry-after header on 429', async () => {
    const res = jsonResponse({}, { status: 429, headers: { 'retry-after': '30' } });
    expect(await rebalanceError(res)).toEqual({ kind: 'key', key: 'errors.tooManyRequestsRetry', params: { n: '30' } });
  });

  it('falls back to a generic key on 429 without retry-after', async () => {
    const res = jsonResponse({}, { status: 429 });
    expect(await rebalanceError(res)).toEqual({ kind: 'key', key: 'errors.tooManyRequests' });
  });

  it('passes a 429 string detail through as raw (backend message)', async () => {
    const res = jsonResponse({ detail: 'slow down' }, { status: 429 });
    expect(await rebalanceError(res)).toEqual({ kind: 'raw', text: 'slow down' });
  });

  it('maps 502 to the market-data key', async () => {
    const res = jsonResponse({}, { status: 502 });
    expect(await rebalanceError(res)).toEqual({ kind: 'key', key: 'errors.marketData' });
  });

  it('maps 502 with a backend detail to the translated market-data key', async () => {
    const res = jsonResponse({ detail: 'Yahoo down' }, { status: 502 });
    expect(await rebalanceError(res)).toEqual({ kind: 'key', key: 'errors.marketData' });
  });

  it('maps any other status to the generic retry key', async () => {
    const res = jsonResponse({}, { status: 500 });
    expect(await rebalanceError(res)).toEqual({ kind: 'key', key: 'errors.requestFailedRetry' });
  });
});

describe('runRebalance', () => {
  const data: RebalanceResponse = {
    results: [],
    total_fees: 0,
    change: 0,
  };

  it('returns the parsed data on 200', async () => {
    const fetchFn = async () => jsonResponse(data, { status: 200 });
    const r = await runRebalance(settings, assets, fetchFn as typeof fetch);
    expect(r).toEqual({ ok: true, data });
  });

  it('returns a mapped error on a non-ok status', async () => {
    const fetchFn = async () => jsonResponse({ detail: 'bad input' }, { status: 422 });
    const r = await runRebalance(settings, assets, fetchFn as typeof fetch);
    expect(r).toEqual({ ok: false, error: { kind: 'key', key: 'errors.validation', params: { detail: 'bad input' } } });
  });

  it('propagates a network failure', async () => {
    const fetchFn = async () => { throw new Error('offline'); };
    await expect(runRebalance(settings, assets, fetchFn as typeof fetch)).rejects.toThrow('offline');
  });
});

describe('runRebalanceInBrowser', () => {
  it('sends only asset identity to /v1/quotes and computes the orders locally', async () => {
    let sent: { url: string; body: unknown } | null = null;
    const fetchFn = async (url: string, init?: RequestInit) => {
      sent = { url, body: JSON.parse(String(init?.body)) };
      return jsonResponse({ base_currency: 'USD', fx_as_of: null, quotes: [{ ticker: 'VOO', price: 100, quote_as_of: '2026-10-27' }] }, { status: 200 });
    };
    const single = [{ ...assets[0], desiredPercentage: 100, fees: 0 }];

    const r = await runRebalanceInBrowser(settings, single, fetchFn as typeof fetch);

    expect(sent).toEqual({ url: '/v1/quotes', body: { base_currency: 'USD', assets: [{ ticker: 'VOO', provider: 'yahoo', currency: 'USD' }] } });
    expect(r.ok && r.data.results[0]).toMatchObject({ ticker: 'VOO', buy: 10, allocated: 1000, quote_as_of: '2026-10-27' });
    expect(r.ok && r.data.change).toBe(0);
  });

  it('rejects negative cash before requesting quotes, as the backend would', async () => {
    let called = false;
    const fetchFn = async () => { called = true; return jsonResponse({}, { status: 200 }); };
    const r = await runRebalanceInBrowser({ ...settings, increment: -50 }, assets, fetchFn as typeof fetch);
    expect(r).toEqual({ ok: false, error: { kind: 'validation', items: [{ key: 'errors.invalid.incrementNegative' }] } });
    expect(called).toBe(false);
  });

  it('maps quote errors like the backend engine', async () => {
    const fetchFn = async () => jsonResponse({ detail: 'Market data unavailable' }, { status: 502 });
    const r = await runRebalanceInBrowser(settings, assets, fetchFn as typeof fetch);
    expect(r).toEqual({ ok: false, error: { kind: 'key', key: 'errors.marketData' } });
  });

  it('propagates a network failure', async () => {
    const fetchFn = async () => { throw new Error('offline'); };
    await expect(runRebalanceInBrowser(settings, assets, fetchFn as typeof fetch)).rejects.toThrow('offline');
  });
});

describe('searchTickers', () => {
  it('returns the results on 200', async () => {
    const results = [{ ticker: 'VOO', name: 'Vanguard S&P 500', exchange: 'NYSE', type: 'etf', provider: 'yahoo', currency: 'USD' }];
    const fetchFn = async () => jsonResponse({ results }, { status: 200 });
    expect(await searchTickers('vo', fetchFn as typeof fetch)).toEqual({ ok: true, results });
  });

  it('defaults to an empty list when results are absent', async () => {
    const fetchFn = async () => jsonResponse({}, { status: 200 });
    expect(await searchTickers('vo', fetchFn as typeof fetch)).toEqual({ ok: true, results: [] });
  });

  it('flags rate limiting on 429', async () => {
    const fetchFn = async () => jsonResponse({}, { status: 429 });
    expect(await searchTickers('vo', fetchFn as typeof fetch)).toEqual({ ok: false, rateLimited: true });
  });

  it('reports a non-rate-limit failure on other non-ok statuses', async () => {
    const fetchFn = async () => jsonResponse({}, { status: 500 });
    expect(await searchTickers('vo', fetchFn as typeof fetch)).toEqual({ ok: false, rateLimited: false });
  });

  it('encodes the query', async () => {
    let calledWith = '';
    const fetchFn = async (url: string) => { calledWith = url; return jsonResponse({ results: [] }, { status: 200 }); };
    await searchTickers('a b&c', fetchFn as unknown as typeof fetch);
    expect(calledWith).toBe('/v1/tickers/search?q=a%20b%26c');
  });

  it('propagates a network failure', async () => {
    const fetchFn = async () => { throw new Error('offline'); };
    await expect(searchTickers('vo', fetchFn as typeof fetch)).rejects.toThrow('offline');
  });
});


it('does not describe an upper-bound violation as a negative value', async () => {
  const response = new Response(JSON.stringify({ detail: [{
    type: 'less_than_equal', loc: ['body', 'assets', 0, 'shares'],
    msg: 'Input should be less than or equal to 1000000000000',
  }] }), { status: 422 });
  expect(await rebalanceError(response)).toEqual({ kind: 'validation', items: [{
    key: 'errors.validation', params: { detail: 'Input should be less than or equal to 1000000000000' },
  }] });
});
