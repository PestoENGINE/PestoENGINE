import { describe, it, expect } from 'vitest';
import { buildRebalanceBody, rebalanceErrorMessage, runRebalance, searchTickers } from './api';
import type { Asset, Settings, RebalanceResponse } from './types';

const settings: Settings = { increment: 1000, onlyBuy: true, optimalRedistribute: false };
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

describe('rebalanceErrorMessage', () => {
  it('joins a 422 array detail', async () => {
    const res = jsonResponse({ detail: [{ msg: 'too low' }, { msg: 'too high' }] }, { status: 422 });
    expect(await rebalanceErrorMessage(res)).toBe('Validation error: too low; too high');
  });

  it('passes through a 422 string detail', async () => {
    const res = jsonResponse({ detail: 'bad input' }, { status: 422 });
    expect(await rebalanceErrorMessage(res)).toBe('Validation error: bad input');
  });

  it('uses the retry-after header on 429', async () => {
    const res = jsonResponse({}, { status: 429, headers: { 'retry-after': '30' } });
    expect(await rebalanceErrorMessage(res)).toBe('Too many requests. Try again in 30 seconds.');
  });

  it('falls back to a generic message on 429 without retry-after', async () => {
    const res = jsonResponse({}, { status: 429 });
    expect(await rebalanceErrorMessage(res)).toBe('Too many requests. Try again shortly.');
  });

  it('prefers a string detail on 429', async () => {
    const res = jsonResponse({ detail: 'slow down' }, { status: 429 });
    expect(await rebalanceErrorMessage(res)).toBe('slow down');
  });

  it('maps 502 to the market-data message', async () => {
    const res = jsonResponse({}, { status: 502 });
    expect(await rebalanceErrorMessage(res)).toBe('Market data unavailable. Check ticker symbols or try again.');
  });

  it('passes through a 502 string detail', async () => {
    const res = jsonResponse({ detail: 'Yahoo down' }, { status: 502 });
    expect(await rebalanceErrorMessage(res)).toBe('Yahoo down');
  });

  it('maps any other status to a generic failure', async () => {
    const res = jsonResponse({}, { status: 500 });
    expect(await rebalanceErrorMessage(res)).toBe('Request failed. Try again.');
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
    expect(r).toEqual({ ok: false, error: 'Validation error: bad input' });
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
