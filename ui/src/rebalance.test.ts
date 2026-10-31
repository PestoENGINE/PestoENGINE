import { describe, expect, it } from 'vitest';
import { computeRebalance } from './rebalance';
import type { Asset, Settings } from './types';

const settings = (patch: Partial<Settings>): Settings => ({
  increment: 0, baseCurrency: 'EUR', onlyBuy: true, optimalRedistribute: false, fractionalShares: false, ...patch,
});

function asset(ticker: string, desiredPercentage: number, shares: number, fees: number): Asset {
  return { id: ticker, ticker, provider: null, currency: null, desiredPercentage, shares, fees, percentageFee: false };
}

const quotes = (...prices: number[]) => ({
  base_currency: 'EUR',
  quotes: prices.map((price, i) => ({ ticker: `T${i}`, price })),
});

describe('light rebalance engine', () => {
  it('buys whole shares net of a flat fee (same case as the backend endpoint test)', () => {
    const r = computeRebalance(settings({ increment: 500 }), [asset('A', 100, 0, 10)], quotes(100));
    expect(r.results[0].buy).toBe(4);
    expect(r.total_fees).toBe(10);
    expect(r.change).toBe(90);
  });

  it('splits cash by gap, then spends the leftover on the most underweight asset', () => {
    const r = computeRebalance(
      settings({ increment: 1000 }),
      [asset('A', 60, 0, 3), asset('B', 40, 0, 2)],
      quotes(50, 100),
    );
    expect(r.results.map(x => x.buy)).toEqual([13, 3]);
    expect(r.total_fees).toBe(5);
    expect(r.change).toBe(45);
  });

  it('spends the leftover with the knapsack DP where greedy strands cash', () => {
    // First pass buys one share of each and leaves 10. Greedy then adds one 6
    // share (4 left); the DP adds two 5 shares (0 left), as in the backend docs.
    const portfolio = [asset('A', 55, 0, 0), asset('B', 45, 0, 0)];
    const greedy = computeRebalance(settings({ increment: 21 }), portfolio, quotes(6, 5));
    const optimal = computeRebalance(settings({ increment: 21, optimalRedistribute: true }), portfolio, quotes(6, 5));
    expect(greedy.results.map(x => x.buy)).toEqual([2, 1]);
    expect(greedy.change).toBe(4);
    expect(optimal.results.map(x => x.buy)).toEqual([1, 3]);
    expect(optimal.change).toBe(0);
  });

  it('gives a tied leftover share to the most underweight asset in both modes', () => {
    // After the first pass 15 is left, enough for one share of either asset.
    // B holds nothing, so it goes first although it is listed second.
    const portfolio = [asset('A', 50, 2, 0), asset('B', 50, 0, 0)];
    for (const optimalRedistribute of [false, true]) {
      const r = computeRebalance(settings({ increment: 35, optimalRedistribute }), portfolio, quotes(10, 10));
      expect(r.results.map(x => x.buy)).toEqual([0, 3]);
      expect(r.change).toBe(5);
    }
  });

  it('funds buys from sales when selling is allowed', () => {
    const r = computeRebalance(
      settings({ onlyBuy: false }),
      [asset('A', 50, 10, 0), asset('B', 50, 0, 0)],
      quotes(100, 100),
    );
    expect(r.results.map(x => x.buy)).toEqual([-5, 5]);
    expect(r.change).toBe(0);
  });

  it.each([
    [false, 999999999500],
    [true, 999999999999.9995],
  ])('keeps quantity rounding within available cash (fractional: %s)', (fractionalShares, increment) => {
    const r = computeRebalance(
      settings({ increment, fractionalShares }),
      [asset('A', 100, 0, 0)],
      quotes(1e12),
    );
    expect(r.results[0].buy * r.results[0].ticker_price + r.total_fees).toBeLessThanOrEqual(increment);
    expect(r.change).toBeGreaterThanOrEqual(0);
  });

  it('retains affordable shares at a floating-point division boundary', () => {
    const r = computeRebalance(settings({ increment: 0.3 }), [asset('A', 100, 0, 0)], quotes(0.1));
    expect(r.results[0].buy).toBe(3);
    expect(r.change).toBeCloseTo(0);
  });

  it('spends sale proceeds at an accumulated floating-point boundary', () => {
    const r = computeRebalance(
      settings({ increment: 333.33, onlyBuy: false }),
      [asset('A', 49, 0, 1), asset('B', 34, 2, 2.5), asset('C', 10, 30, 1), asset('D', 7, 10, 1)],
      quotes(148.35, 62.88, 13.7, 43.71),
    );
    expect(r.results.map(x => x.buy)).toEqual([4, 5, -20, -7]);
    expect(r.change).toBe(0);
  });

  it('does not let unsold holdings inflate the cash rounding tolerance', () => {
    const r = computeRebalance(
      settings({ increment: 999999999500 }),
      [asset('A', 0, 1e12, 0), asset('B', 100, 0, 0)],
      quotes(1e12, 1e12),
    );
    expect(r.results.map(x => x.buy)).toEqual([0, 0]);
    expect(r.change).toBe(999999999500);
  });

  it.each([1, 100, 1e10])('optimizes affordable shares at currency scale %s without counting impossible candidates', scale => {
    const portfolio = Array.from({ length: 100 }, (_, i) => asset(`A${i}`, 1, 0, i < 2 ? 5 * scale : 0));
    const r = computeRebalance(
      settings({ increment: 100 * scale, optimalRedistribute: true }),
      portfolio,
      quotes(60 * scale, 45 * scale, ...Array(98).fill(200 * scale)),
    );
    expect(r.results.map(x => x.buy)).toEqual([0, 2, ...Array(98).fill(0)]);
    expect(r.total_fees).toBe(5 * scale);
    expect(r.change).toBe(5 * scale);
  });

  it('skips redistribution when no target has a positive gap', () => {
    const portfolio = Array.from({ length: 100 }, (_, i) => asset(`A${i}`, 1, 1e12, 0));
    const r = computeRebalance(
      settings({ increment: 1e9, optimalRedistribute: true }),
      portfolio,
      quotes(...Array(100).fill(1e12)),
    );
    expect(r.results.every(x => x.buy === 0)).toBe(true);
    expect(r.change).toBe(1e9);
  });
});
