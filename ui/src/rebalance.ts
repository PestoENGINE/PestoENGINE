/**
 * Light rebalance engine, used when the backend sets REBALANCE_ENGINE=frontend.
 *
 * A simplified version of the backend calculation (app/rebalance/): same target
 * gaps, capped sales, fees and proportional split of the cash, then leftover cash
 * spent on whole shares, greedily or with the knapsack DP. Plain float arithmetic,
 * a DP grid in cents and one priority order for both passes, so results can
 * differ slightly from the backend.
 */
import type { Asset, AssetResultOut, QuotesResponse, RebalanceResponse, Settings } from './types';

// Same safety limit as the backend DP: candidates x capacity cells.
const MAX_DP_WORK = 1_000_000;

const sum = (values: number[]): number => values.reduce((s, v) => s + v, 0);
const round2 = (x: number): number => Math.round(x * 100) / 100;
// Round a quantity down; the epsilon keeps 0.29 * 100 at 29 shares, not 28.
const floorTo = (x: number, places: number): number => Math.floor(x * 10 ** places + 1e-9) / 10 ** places;

/** An underweight asset that can receive extra whole shares from leftover cash. */
interface Extra {
  i: number; // index in the portfolio
  unit: number; // cost of one share, percentage fee included
  opening: number; // flat fee, paid only if this opens the position
}

interface Picked {
  counts: number[];
  cash: number;
}

/** In priority order, as many shares as the cash allows. */
function greedyExtras(extras: Extra[], cash: number): Picked {
  const counts = extras.map(({ unit, opening }) => {
    const count = floorTo(Math.max(0, cash - opening) / unit, 0);
    if (count > 0) cash -= count * unit + opening;
    return count;
  });
  return { counts, cash };
}

/**
 * Unbounded knapsack in cents: the extra shares that spend the most cash, a flat
 * fee charged once per opened position. On equal spend the asset earlier in
 * priority order keeps the cash. Null when the grid is too large; the caller
 * then keeps the greedy result.
 */
function knapsackExtras(extras: Extra[], cash: number): Picked | null {
  const size = Math.floor(cash * 100 + 1e-9) + 1;
  if (extras.length * size > MAX_DP_WORK) return null;
  // Round costs up, to at least a cent, so every pick is affordable in full precision.
  const cents = (x: number) => Math.max(1, Math.ceil(x * 100 - 1e-9));
  const layers = extras.map(({ unit, opening }) => ({
    unit: cents(unit),
    first: cents(unit) + (opening ? cents(opening) : 0),
    pick: new Int32Array(size), // shares of this asset in the best solution at each capacity
  }));

  let best = new Int32Array(size); // most cents spent at each capacity by the assets so far
  for (const { unit, first, pick } of layers) {
    // Best spend holding at least one share of this asset: open the position
    // here, fee included, or add a share to one opened below. Unreachable
    // states (-1) never win, since opening alone spends at least `first`.
    const open = new Int32Array(size).fill(-1);
    const count = new Int32Array(size);
    const next = best.slice();
    for (let k = first; k < size; k++) {
      open[k] = best[k - first] + first;
      count[k] = 1;
      if (open[k - unit] + unit > open[k]) {
        open[k] = open[k - unit] + unit;
        count[k] = count[k - unit] + 1;
      }
      if (open[k] > next[k]) {
        next[k] = open[k];
        pick[k] = count[k];
      }
    }
    best = next;
  }

  const counts = extras.map(() => 0);
  let k = size - 1;
  for (let m = layers.length - 1; m >= 0; m--) {
    const { unit, first, pick } = layers[m];
    counts[m] = pick[k];
    if (pick[k]) k -= first + (pick[k] - 1) * unit;
  }
  const cost = sum(extras.map((e, m) => (counts[m] ? counts[m] * e.unit + e.opening : 0)));
  return { counts, cash: cash - cost };
}

export function computeRebalance(settings: Settings, assets: Asset[], quotes: QuotesResponse): RebalanceResponse {
  const prices = quotes.quotes.map(q => q.price);
  const places = settings.fractionalShares ? 6 : 0;
  const values = assets.map((a, i) => a.shares * prices[i]);
  const total = sum(values);
  const current = values.map(v => (total ? (v * 100) / total : 0));
  const targetTotal = total + settings.increment;
  const unitCost = (i: number) => prices[i] * (assets[i].percentageFee ? 1 + assets[i].fees / 100 : 1);
  const fee = (i: number, quantity: number) => {
    if (!quantity) return 0;
    return assets[i].percentageFee ? (Math.abs(quantity) * prices[i] * assets[i].fees) / 100 : assets[i].fees;
  };

  // How far each asset is from its target value once the new cash is added.
  const gaps = assets.map((a, i) => (targetTotal * a.desiredPercentage) / 100 - values[i]);
  const quantities = assets.map(() => 0);
  let cash = settings.increment;

  if (!settings.onlyBuy) {
    // Sell overweight positions, never more than is held, to fund the buys.
    gaps.forEach((gap, i) => {
      if (gap >= 0) return;
      const sold = floorTo(Math.min(-gap / prices[i], assets[i].shares), places);
      const proceeds = sold * prices[i] - fee(i, sold);
      if (sold > 0 && proceeds > 0) {
        quantities[i] = -sold;
        cash += proceeds;
      }
    });
  }

  // Split the cash among underweight assets in proportion to their gap.
  const positive = sum(gaps.filter(g => g > 0));
  const budget = Math.min(cash, positive);
  gaps.forEach((gap, i) => {
    if (gap <= 0) return;
    const opening = assets[i].percentageFee ? 0 : assets[i].fees;
    const allowance = Math.min(cash, (budget * gap) / positive);
    const bought = floorTo(Math.max(0, allowance - opening) / unitCost(i), places);
    if (bought > 0) {
      quantities[i] = bought;
      cash -= bought * prices[i] + fee(i, bought);
    }
  });

  if (!settings.fractionalShares) {
    // Spend the leftover on extra whole shares of the underweight assets, the
    // lowest current / target weight first (the backend's greedy priority).
    const ratio = (i: number) => current[i] / (assets[i].desiredPercentage + 0.01);
    const extras: Extra[] = assets
      .map((a, i) => ({ i, unit: unitCost(i), opening: quantities[i] === 0 && !a.percentageFee ? a.fees : 0 }))
      .filter(e => gaps[e.i] > 0)
      .sort((x, y) => ratio(x.i) - ratio(y.i));
    let picked = greedyExtras(extras, cash);
    if (settings.optimalRedistribute) {
      // Like the backend: keep the DP only if it leaves no more cash than greedy.
      const dp = knapsackExtras(extras, cash);
      if (dp && dp.cash <= picked.cash + 1e-9) picked = dp;
    }
    picked.counts.forEach((count, m) => { quantities[extras[m].i] += count; });
    cash = picked.cash;
  }

  const fees = quantities.map((q, i) => fee(i, q));
  const results: AssetResultOut[] = assets.map((a, i) => ({
    id: i,
    ticker: quotes.quotes[i].ticker,
    current_percentage: round2(current[i]),
    desired_percentage: a.desiredPercentage,
    shares: a.shares,
    allocated: round2(quantities[i] * prices[i]),
    ticker_price: prices[i],
    fees: round2(fees[i]),
    buy: quantities[i],
    quote_as_of: quotes.quotes[i].quote_as_of ?? null,
  }));

  return {
    results,
    total_fees: round2(sum(fees)),
    change: round2(cash),
    base_currency: quotes.base_currency,
    fx_as_of: quotes.fx_as_of ?? null,
  };
}
