"""Pure target-allocation and whole-share redistribution algorithms.

The calculation has two distinct stages:
    1. calculate_rebalance() computes theoretical currency amounts from the
       portfolio's target weights and the new cash contribution.
    2. The order planner in orders.py turns those amounts into funded trades,
       accounting for holdings, fees and quantity rounding. It calls one of
       the redistribution functions here to spend remaining whole-share cash.

These functions perform no I/O and do not fetch prices or convert currencies.
All monetary inputs must already use the same currency, and parallel lists
must describe the same assets in the same order. Request validation belongs
to the API boundary; the order planner supplies financially feasible inputs.
"""

from array import array
from decimal import ROUND_CEILING, Decimal

from app.core.formatting import as_decimal

# Maximum DP capacity in scaled currency units. The historical name refers to
# cents, but the adaptive scale can retain more than two decimal places.
MAX_CENTS = 100_000
# Also cap candidate-count * capacity: a capacity-only limit would allow work
# and reconstruction storage to grow without bound as assets are added.
MAX_DP_WORK = 1_000_000
_ZERO = Decimal(0)
_HUNDRED = Decimal(100)


def _decimals(values: list[Decimal | int | float]) -> list[Decimal]:
    """Normalize numeric inputs through their decimal representation."""
    return [as_decimal(value) for value in values]


def _decimal_places(value: Decimal) -> int:
    """Return significant fractional places without trailing zeroes."""
    normalized = value.normalize()
    return max(0, -normalized.as_tuple().exponent)


def _redistribute_proportional_to_gap(
    values: list[Decimal | int | float],
    percentages: list[Decimal | int | float],
    increment: Decimal | int | float,
) -> list[Decimal]:
    """Distribute the increment proportionally to each asset's positive rebalance gap.

    Used in only_buy mode.

    For every asset the gap measures how far its current value sits from its ideal
    post-increment target value.  Overweight assets (negative gap) receive nothing;
    underweight assets (positive gap) share the increment in proportion to their gap.
    Eligibility is measured against the portfolio AFTER adding the increment.
    An asset already at its current target percentage can therefore still have
    a positive monetary gap and receive some of the new cash.

    Decision variables:
        v_i    -- current monetary value of asset i
        t_i    -- target allocation weight for asset i (%)
        Delta  -- new cash to distribute (increment)
        T      -- post-increment total:  T = sum(v_i) + Delta

    Gap formula:
        g_i = T * (t_i / 100) - v_i

        A key identity holds when weights sum to 100 %:
            sum(g_i) = Delta

        g_i > 0  means asset i is underweight  -> eligible to receive money.
        g_i <= 0 means asset i is overweight   -> excluded (buy-only constraint).

    Allocation policy:
        Assign a_i to each eligible asset proportionally to its positive gap.
        This is a cash-allocation heuristic, not an optimisation of final drift.

    Allocation formula:
        S+  = sum(g_i  for all i where g_i > 0)
        a_i = Delta * (g_i / S+)   if g_i > 0
            = 0                    otherwise

        In exact arithmetic, sum(a_i) = Delta * (S+ / S+) = Delta when S+ > 0.
        Decimal division can round at the active context precision. These are
        theoretical budgets; executable quantities, fees and residual cash
        are determined later by orders.py.

    Formal algorithm (3 steps):
        1. Compute T = sum(values) + increment and g_i for every asset.
        2. Sum only the positive gaps into S+.  If S+ == 0 (no positive gap),
           return a zero vector -- no eligible asset exists.
        3. For each asset i:
               if g_i > 0:  a_i = Delta * (g_i / S+)
               else:        a_i = 0

    Example - values [0, 40, 100, 100], targets [60, 20, 10, 10], increment 100:
        T    = 340
        g_A  = 340 * 0.60 - 0   = +204
        g_B  = 340 * 0.20 - 40  =  +28
        g_C  = 340 * 0.10 - 100 =  -66  -> 0
        g_D  = 340 * 0.10 - 100 =  -66  -> 0
        S+   = 232
        a_A  = 100 * 204/232, approximately 87.93
        a_B  = 100 * 28/232, approximately 12.07

    Complexity: O(n), two linear passes over the computed gaps vector
    (one to sum positive gaps, one to allocate); building the gaps
    vector and summing the raw values each add one further O(n) pass,
    so the total is a constant number of linear passes.

    Args:
        values: Current monetary value held in each asset.
        percentages: Target allocation percentages, aligned with values.
        increment: Total new cash to distribute (Delta).

    Returns:
        Theoretical amounts per asset; non-positive gaps receive zero, while
        positive gaps share the increment subject to Decimal context precision.
    """
    values_d = _decimals(values)
    percentages_d = _decimals(percentages)
    increment_d = as_decimal(increment)
    # New cash changes the monetary targets even before any shares are bought.
    total_value = sum(values_d) + increment_d
    gaps = [(total_value * p / _HUNDRED) - v for p, v in zip(percentages_d, values_d)]

    # Exclude sale targets from the denominator: a buy-only contribution must
    # be distributed entirely among assets that can receive a purchase.
    total_positive = sum(g for g in gaps if g > _ZERO)
    if total_positive == _ZERO:
        return [_ZERO] * len(values_d)

    return [increment_d * (g / total_positive) if g > _ZERO else _ZERO for g in gaps]


def calculate_rebalance(
    only_buy: bool,
    increment: Decimal | int | float,
    values: list[Decimal | int | float],
    percentages: list[Decimal | int | float],
) -> list[Decimal]:
    """Calculate theoretical rebalance amounts for each portfolio holding.

    With sales enabled, each signed amount is its post-contribution target
    value minus its current value:

        T   = sum(values) + increment
        r_i = T * percentages_i / 100 - values_i

    A positive r_i requests a purchase; a negative r_i requests a sale. When
    the weights sum to 100, sum(r_i) equals increment in exact arithmetic.
    In buy-only mode, distribute increment over positive gaps instead.

    This function does not reserve fees, round shares or guarantee that a sale
    will execute for its theoretical amount. orders.py handles those constraints
    before using any sale proceeds to fund buys. Time and space are O(n).

    Args:
        only_buy: When True, disallow selling. The increment is distributed
            only among underweight holdings proportional to their gap.
        increment: Additional cash being invested this period.
        values: Current monetary value held in each asset.
        percentages: Target allocation percentage for each asset (must sum to 100).

    Returns:
        Currency amounts to invest/divest per holding.
        In only_buy mode all amounts are >= 0.
    """
    if only_buy:
        return _redistribute_proportional_to_gap(values, percentages, increment)
    values_d = _decimals(values)
    percentages_d = _decimals(percentages)
    total_value = sum(values_d) + as_decimal(increment)
    return [(total_value * p / _HUNDRED) - v for p, v in zip(percentages_d, values_d)]


def redistribute_change(
    buy_quantities: list[int],
    ticker_prices: list[Decimal | int | float],
    current_percentages: list[Decimal | int | float],
    desired_percentages: list[Decimal | int | float],
    change: Decimal | int | float,
    *,
    eligible: list[bool] | None = None,
    opening_fees: list[Decimal] | None = None,
) -> tuple[list[int], Decimal]:
    """Redistribute leftover cash using greedy underweight priority.

    The order planner has already reserved the cost and fees of initial orders.
    This pass can add whole shares to eligible purchases, including an initial
    zero quantity when the explicit eligibility mask allows opening a position.
    It never changes an existing sale into a purchase.

    Decision variables:
        q_i     -- initial signed whole-share order quantity
        x_i     -- additional shares, an integer >= 0
        p_i     -- marginal cost of one extra share, including percentage fees
        f_i     -- flat opening fee if q_i == 0; otherwise zero
        c       -- cash still available after funding the initial orders

    Constraints:
        sum(p_i * x_i + f_i * [x_i > 0]) <= c
        x_i = 0 for excluded assets, existing sales or non-positive prices

    The indicator [x_i > 0] ensures that an opening fee is paid only if a
    purchase is actually made. Flat fees on existing buys are already funded;
    do not charge them again when adding more shares to that same order.

    Eligibility:
        With eligible=None, retain the historical policy q_i > 0.
        With an explicit mask, the caller chooses the allowed assets. The order
        planner supplies positive target gaps to both Greedy and DP, including
        orders that rounded down to zero during the first allocation pass.

    Formal algorithm:
        1. Sort assets by current_i / (desired_i + 0.01), ascending. A smaller
           ratio has higher priority; 0.01 avoids division by zero. Input order
           breaks ties deterministically. These priorities stay fixed.
        2. For each eligible asset, calculate:
               x_i = floor(max(0, remaining_cash - f_i) / p_i)
        3. If x_i > 0, add those shares and subtract p_i * x_i + f_i.
        4. Return updated quantities and the remaining cash.

    Example:
        Initial orders [0, 0], prices [60, 60], flat fees [5, 5], cash 100,
        both assets explicitly eligible and equally prioritised:
        the first asset receives one share for 65, leaving 35. The second
        cannot open a position. Its fee is not charged.

    This one-pass heuristic does not guarantee minimum cash or minimum final
    allocation drift. Redistribution can exceed individual target weights.
    Time is O(n log n) for sorting; additional space is O(n).

    Args:
        buy_quantities: Initial whole-share orders; negative values are sales.
        ticker_prices: Per-share marginal costs in the calculation currency.
        current_percentages: Current portfolio weights used for priority.
        desired_percentages: Target weights used for priority.
        change: Available cash after funding initial orders and their fees.
        eligible: Optional per-asset permission to add shares.
        opening_fees: Per-asset flat fees, used only for initially zero orders;
            None means no opening fees. Percentage fees belong in ticker_prices.

    Returns:
        Updated order quantities and unspent cash. Inputs are not mutated.
    """
    prices = _decimals(ticker_prices)
    current = _decimals(current_percentages)
    desired = _decimals(desired_percentages)
    remaining = as_decimal(change)
    updated = list(buy_quantities)
    # An explicit positive-gap mask allows purchases that originally rounded
    # to zero; merely checking q_i > 0 would strand otherwise investable cash.
    mask = eligible if eligible is not None else [q > 0 for q in updated]
    fees = opening_fees or [_ZERO] * len(updated)
    # Lower current/desired ratio receives priority. Sorting is stable on ties.
    for i in sorted(range(len(updated)), key=lambda i: current[i] / (desired[i] + Decimal("0.01"))):
        if not mask[i] or updated[i] < 0 or prices[i] <= 0 or remaining <= 0:
            continue
        # Reserve a flat fee before testing affordability, but only deduct it
        # when at least one extra share is bought. Existing buys paid it already.
        opening = fees[i] if updated[i] == 0 else _ZERO
        extra = int(max(_ZERO, remaining - opening) // prices[i])
        if extra:
            remaining -= extra * prices[i] + opening
            updated[i] += extra
    return updated, remaining


def redistribute_change_optimal(
    only_buy: bool,
    buy_quantities: list[int],
    ticker_prices: list[Decimal | int | float],
    current_percentages: list[Decimal | int | float],
    desired_percentages: list[Decimal | int | float],
    change: Decimal | int | float,
    *,
    eligible: list[bool] | None = None,
    opening_fees: list[Decimal] | None = None,
) -> tuple[list[int], Decimal]:
    """Maximise affordable spend using layered unbounded-knapsack DP.

    Greedy commits to one asset at a time and can strand affordable cash.
    Dynamic programming considers combinations of additional whole shares.
    Share counts are unbounded except by the available cash; computation and
    reconstruction storage are bounded by the safety limits below.

    Financial model and eligibility:
        Use the same q_i, p_i, f_i and cash convention as redistribute_change().
        Initial orders are already funded; only additional costs consume change.
        Each asset's flat opening fee is paid once, on its first extra share,
        and only when its initial order is zero. Existing sales stay unchanged.

        An explicit eligible mask is authoritative for both DP and its greedy
        baseline. The order planner supplies positive monetary gaps to both.
        Without a mask, retain the historical direct-call policy:
            only_buy=False: q_i > 0
            only_buy=True:  q_i > 0 and current_i < desired_i

    Scaled problem formulation:
        s   = 10**places, retaining at least two decimal places
        W   = floor(change * s), the integer capacity
        P_i = ceil(p_i * s), the marginal cost per extra share
        F_i = ceil(f_i * s), the one-time opening fee
        w_i = desired_i - current_i, the tie score per extra share

        Choose integer x_i >= 0 for eligible assets to maximise:
            S(x) = sum(P_i * x_i + F_i * [x_i > 0]), subject to S(x) <= W.
        Among equal S(x), maximise sum(w_i * x_i).

        The primary objective includes fees: it minimises unspent cash at the
        chosen scale, not fees or final allocation drift. Ties with equal spend
        and equal weight score keep the first encountered solution.

    Dynamic programming, one layer per candidate asset:
        spent[k], tie[k] store the best solution using PREVIOUS assets and a
        capacity of k. Initially all capacities permit only the empty solution.

        For the current asset i, active_spent[k] and active_tie[k] describe
        solutions using AT LEAST ONE extra share of i. Unreachable active
        states use spent=-1. Let first = P_i + F_i. At each k >= first:

            Open:   previous[k - first] + (first, w_i)
            Extend: active[k - P_i] + (P_i, w_i), if reachable

        Compare (spent, tie) lexicographically. The open transition starts from
        the previous layer and pays F_i once. The extend transition stays in
        the active layer and adds only P_i, so later shares cannot repeat F_i.

        The next layer then chooses between previous[k] (zero extra shares of
        i) and active[k] (one or more). selected[k] records the chosen count
        of i for reconstruction; zero means the previous solution was retained.

    Reconstruction:
        Start at W and visit the saved layers in reverse order. If the selected
        count is x_i > 0, add it to the initial order and subtract
        first + (x_i - 1) * P_i from k. The resulting k is the capacity in the
        previous layer. Recompute the final cost from the original Decimal
        prices and opening fees, not from the rounded-up scaled costs.

    Example without opening fees:
        Initial orders [1, 1], prices [6, 5], cash 10, both assets eligible,
        with the first asset prioritised by Greedy: Greedy adds one share at 6
        and leaves 4. DP adds two shares of the second asset and leaves zero.

    Precision and safety limits:
        For m candidates, cap = min(MAX_CENTS, MAX_DP_WORK // m).
        Start with the precision of prices/fees and reduce it while necessary,
        keeping at least two places. If W still exceeds cap, return Greedy.
        Rounding costs up and cash down makes DP conservative: it can exclude
        combinations affordable at full precision. Compare its exact remainder
        against the same-mask, same-fee Greedy result and return Greedy if that
        spends more. The returned result therefore leaves no more cash than
        that baseline, but is not necessarily an exact full-precision optimum.

    Complexity:
        Time O(n log n + m * W), including the greedy baseline.
        Space O(n + m * W): working score arrays need O(W), while saved counts
        for backtracking need O(m * W). Both m and W affect the safety bound.

    Args:
        only_buy: Controls default eligibility only when no explicit mask exists.
        buy_quantities: Initial whole-share orders, including any unchanged sales.
        ticker_prices: Marginal per-share costs, including percentage fees.
        current_percentages: Current weights used for tie scores and Greedy.
        desired_percentages: Target weights used for tie scores and Greedy.
        change: Cash remaining after initial orders and their fees.
        eligible: Optional per-asset permission shared with the greedy baseline.
        opening_fees: Optional flat fees for initially zero orders.

    Returns:
        Updated quantities and remaining cash calculated from Decimal costs.
        If no additional share is affordable, return the initial orders/cash.

    See Also:
        redistribute_change(): the cheaper O(n log n) redistribution heuristic.
    """
    prices = _decimals(ticker_prices)
    current = _decimals(current_percentages)
    desired = _decimals(desired_percentages)
    cash = as_decimal(change)
    # Resolve eligibility once. In particular, a safety fallback must not
    # accidentally re-enable an asset excluded by the caller or buy-only policy.
    mask = (
        eligible
        if eligible is not None
        else [
            q > 0 and (not only_buy or c < d) for q, c, d in zip(buy_quantities, current, desired)
        ]
    )
    fees = opening_fees or [_ZERO] * len(prices)
    # Keep an affordable baseline for both workload fallback and the final
    # comparison after conservative integer scaling.
    greedy = redistribute_change(
        buy_quantities,
        prices,
        current,
        desired,
        cash,
        eligible=mask,
        opening_fees=fees,
    )
    # Include an initially zero order if its first share AND opening fee fit.
    # Existing sales and invalid prices cannot become additional purchases.
    candidates = [
        i
        for i, price in enumerate(prices)
        if mask[i]
        and buy_quantities[i] >= 0
        and price > 0
        and price + (fees[i] if buy_quantities[i] == 0 else 0) <= cash
    ]
    if cash <= 0 or not candidates:
        return greedy
    # Bound the product of candidate count and scaled capacity before creating
    # any DP arrays. More assets mean a smaller permitted capacity per layer.
    cap = min(MAX_CENTS, MAX_DP_WORK // len(candidates))
    places = max(
        2,
        *(_decimal_places(prices[i]) for i in candidates),
        *(_decimal_places(fees[i]) for i in candidates),
    )
    # Preserve sub-cent prices where affordable. The two-place minimum avoids
    # silently reducing monetary precision to whole currency units.
    scale = Decimal(10) ** places
    while places > 2 and cash * scale > cap:
        places -= 1
        scale /= 10
    capacity = int(cash * scale)
    if capacity > cap:
        return greedy
    # Previous-layer solutions initially spend zero at every capacity. Each
    # layer saves only counts for backtracking; score arrays can be replaced.
    size = capacity + 1
    spent = [0] * size
    tie = [_ZERO] * size
    layers = []
    costs = []
    for i in candidates:
        # Round both cost components upward. Reserving the flat fee separately
        # ensures it is charged once even when several extra shares are chosen.
        price = int((prices[i] * scale).to_integral_value(rounding=ROUND_CEILING))
        opening = fees[i] if buy_quantities[i] == 0 else _ZERO
        first = price + int((opening * scale).to_integral_value(rounding=ROUND_CEILING))
        weight = desired[i] - current[i]
        # Active states must contain this asset. -1 distinguishes unreachable
        # states from a valid previous-layer solution that spends zero.
        active_spent = [-1] * size
        active_tie = [_ZERO] * size
        active_count = array("i", [0]) * size
        selected = array("i", [0]) * size
        next_spent = spent.copy()
        next_tie = tie.copy()
        for k in range(first, size):
            # Open a position in this layer, paying first-share cost once.
            best_spent = spent[k - first] + first
            best_tie = tie[k - first] + weight
            count = 1
            if k >= price and active_spent[k - price] >= 0:
                # Extend a reachable position; its opening fee was already paid.
                more = (active_spent[k - price] + price, active_tie[k - price] + weight)
                if more > (best_spent, best_tie):
                    best_spent, best_tie = more
                    count = active_count[k - price] + 1
            active_spent[k], active_tie[k], active_count[k] = best_spent, best_tie, count
            # Spending wins before weight score. On a complete tie, retain the
            # previous-layer solution and its zero count for the current asset.
            if (best_spent, best_tie) > (spent[k], tie[k]):
                next_spent[k], next_tie[k], selected[k] = best_spent, best_tie, count
        spent, tie = next_spent, next_tie
        layers.append(selected)
        costs.append((first, price))
    # Follow saved counts backwards to the matching previous-layer capacity.
    updated = list(buy_quantities)
    k = capacity
    for i, selected, (first, price) in reversed(list(zip(candidates, layers, costs))):
        count = selected[k]
        if count:
            updated[i] += count
            k -= first + (count - 1) * price
    # Integer units were only a conservative search grid. Report exact Decimal
    # costs and apply an opening fee only to orders actually opened by this pass.
    exact_cost = sum(
        (updated[i] - buy_quantities[i]) * prices[i]
        + (fees[i] if updated[i] > 0 and buy_quantities[i] == 0 else _ZERO)
        for i in candidates
    )
    remaining = cash - exact_cost
    # Scaling can make DP miss a cheaper exact combination already found by
    # Greedy. Never return more leftover cash than the same-policy baseline.
    return greedy if greedy[1] < remaining else (updated, remaining)
