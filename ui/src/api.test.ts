import { describe, it, expect } from 'vitest';
import { buildRebalanceBody, rebalanceError, runRebalance, searchTickers } from './api';
import type { Asset, Settings, RebalanceResponse } from './types';

const settings: Settings = { increment: 1000, onlyBuy: true, optimalRedistribute: false, fractionalShares: false };
const assets: Asset[] = [
  { id: 'a1', ticker: 'VOO', provider: 'yahoo', desiredPercentage: 60, shares: 10, fees: 0.5, percentageFee: true },
];

function jsonResponse(body: unknown, init: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'content-type': 'application/json' },
    ...init,
  });
}

describe('buildRebalanceBody', () => {
  it('maps camelCase settings/assets to snake_case', () => {
    expect(buildRebalanceBody(settings, assets)).toEqual({
      only_buy: true,
      increment: 1000,
      optimal_redistribute: false,
      fractional_shares: false,
      assets: [
        { ticker: 'VOO', provider: 'yahoo', desired_percentage: 60, shares: 10, fees: 0.5, percentage_fee: true },
      ],
    });
  });

  it('defaults a missing provider to null', () => {
    const body = buildRebalanceBody(settings, [{ ...assets[0], provider: null }]);
    expect(body.assets[0].provider).toBeNull();
  });
});

describe('rebalanceError', () => {
  it('joins a 422 array detail into the validation key', async () => {
    const res = jsonResponse({ detail: [{ msg: 'too low' }, { msg: 'too high' }] }, { status: 422 });
    expect(await rebalanceError(res)).toEqual({ kind: 'key', key: 'errors.validation', params: { detail: 'too low; too high' } });
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

  it('passes a 502 string detail through as raw (backend message)', async () => {
    const res = jsonResponse({ detail: 'Yahoo down' }, { status: 502 });
    expect(await rebalanceError(res)).toEqual({ kind: 'raw', text: 'Yahoo down' });
  });

  it('maps any other status to the generic retry key', async () => {
    const res = jsonResponse({}, { status: 500 });
    expect(await rebalanceError(res)).toEqual({ kind: 'key', key: 'errors.requestFailedRetry' });
  });
});

describe('runRebalance', () => {
  const data: RebalanceResponse = { results: [], total_fees: 0, change: 0 };

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

describe('searchTickers', () => {
  it('returns the results on 200', async () => {
    const results = [{ ticker: 'VOO', name: 'Vanguard S&P 500', exchange: 'NYSE', type: 'etf', provider: 'yahoo' }];
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
