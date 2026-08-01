"""Core functions for portfolio rebalancing calculations."""

from decimal import ROUND_CEILING, Decimal

from app.core.formatting import as_decimal

# DP safety cap: above this many scaled units, fall back to greedy.
MAX_CENTS = 1_000_000
_ZERO = Decimal(0)
_HUNDRED = Decimal(100)


def _decimals(values: list[Decimal | int | float]) -> list[Decimal]:
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
    This is a practical heuristic known as Proportional Redistribution on Positive
    Gaps, commonly used in cash-flow and smart-contribution rebalancing algorithms.

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

    Objective (implicitly maximised):
        Allocate a_i to each eligible asset proportionally to its positive gap,
        spending exactly Delta and producing the smoothest gradient towards target.

    Allocation formula:
        S+  = sum(g_i  for all i where g_i > 0)
        a_i = Delta * (g_i / S+)   if g_i > 0
            = 0                    otherwise

        Conservation: sum(a_i) = Delta * (S+ / S+) = Delta (no money lost).

    Formal algorithm (3 steps):
        1. Compute T = sum(values) + increment and g_i for every asset.
        2. Sum only the positive gaps into S+.  If S+ == 0 (all assets overweight),
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
        a_A  = 100 * 204/232 = 87.93;  a_B = 100 * 28/232 = 12.07

    Complexity: O(n), two linear passes over the computed gaps vector
    (one to sum positive gaps, one to allocate); building the gaps
    vector and summing the raw values each add one further O(n) pass,
    so the total is a constant number of linear passes.

    Args:
        values: Current monetary value held in each asset.
        percentages: Target allocation percentages, aligned with values.
        increment: Total new cash to distribute (Delta).

    Returns:
        Allocation amounts per asset; overweight assets receive 0, underweight
        assets receive amounts summing exactly to increment.
    """
    values_d = _decimals(values)
    percentages_d = _decimals(percentages)
    increment_d = as_decimal(increment)
    total_value = sum(values_d) + increment_d
    gaps = [
        (total_value * p / _HUNDRED) - v
        for p, v in zip(percentages_d, values_d)
    ]

    total_positive = sum(g for g in gaps if g > _ZERO)
    if total_positive == _ZERO:
        return [_ZERO] * len(values_d)

    return [
        increment_d * (g / total_positive) if g > _ZERO else _ZERO
        for g in gaps
    ]


def calculate_rebalance(
    only_buy: bool,
    increment: Decimal | int | float,
    values: list[Decimal | int | float],
    percentages: list[Decimal | int | float],
) -> list[Decimal]:
    """Calculate the optimal rebalance amounts for each portfolio holding.

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
    return [
        (total_value * p / _HUNDRED) - v
        for p, v in zip(percentages_d, values_d)
    ]


def redistribute_change(
    buy_quantities: list[int],
    ticker_prices: list[Decimal | int | float],
    current_percentages: list[Decimal | int | float],
    desired_percentages: list[Decimal | int | float],
    change: Decimal | int | float,
) -> tuple[list[int], Decimal]:
    """Redistribute leftover cash from discrete share purchases.

    After converting currency amounts to whole share counts via floor division,
    there is typically some cash left over. This function allocates that change
    to eligible assets, prioritising those furthest below their target allocation.

    Only assets that already have a non-zero buy quantity are eligible, preventing
    unintended purchases in assets intentionally excluded from the current round.

    Algorithm:
        This function implements a greedy algorithm for the Unbounded Integer Knapsack
        Problem adapted to portfolio underweight prioritisation (sometimes called the
        Greedy Assignment by Underweight Priority method in portfolio rebalancing).

    Decision variables:
        x_i  in  Z≥0  -- extra shares to buy for asset i
        q_i^0         -- initial whole-share buy quantity for asset i
        p_i           -- price per share for asset i
        c             -- leftover cash (change)

    Objective (implicitly maximised):
        Maximise  Σ w_i · x_i,   w_i ∝ (desired_i + ε) / current_i

        A higher w_i means the asset is further below its target allocation.

    Constraints:
        Capacity:    Σ p_i · x_i ≤ c
        Eligibility: x_i = 0 whenever q_i^0 ≤ 0 (only buy what was already scheduled)
        Integrality: x_i ∈ Z≥0

    Formal algorithm (4 steps):
        1. Compute priority ratio  k_i = current_i / (desired_i + ε)  for every asset.
           A low ratio means the asset is heavily underweight (high urgency).
        2. Sort asset indices in ascending order of k_i.
        3. For each index i in that order:
               if q_i^0 > 0:  x_i = floor(c_remaining / p_i)
                              c_remaining -= x_i · p_i
               else:          x_i = 0
        4. Return updated quantities and c_remaining.

    Complexity: O(n log n) dominated by the sort in step 2.

    Args:
        buy_quantities: Whole share counts to purchase per asset.
        ticker_prices: Current price per share for each asset.
        current_percentages: Current portfolio weight of each asset (%).
        desired_percentages: Target portfolio weight of each asset (%).
        change: Leftover cash to allocate.

    Returns:
        A tuple of (updated buy quantities, remaining unallocated change).
    """
    ticker_prices_d = _decimals(ticker_prices)
    current_percentages_d = _decimals(current_percentages)
    desired_percentages_d = _decimals(desired_percentages)
    change_d = as_decimal(change)
    if change_d <= _ZERO:
        return list(buy_quantities), change_d

    # ε avoids division-by-zero; lower ratio = more underweight = higher priority.
    epsilon = Decimal("0.01")
    sorted_indices = sorted(
        range(len(buy_quantities)),
        key=lambda i: current_percentages_d[i] / (desired_percentages_d[i] + epsilon),
    )

    updated = list(buy_quantities)
    remaining = change_d
    for i in sorted_indices:
        if updated[i] <= 0:
            continue
        x_i = int(remaining // ticker_prices_d[i])
        remaining -= x_i * ticker_prices_d[i]
        updated[i] += x_i

    return updated, remaining


def redistribute_change_optimal(
    only_buy: bool,
    buy_quantities: list[int],
    ticker_prices: list[Decimal | int | float],
    current_percentages: list[Decimal | int | float],
    desired_percentages: list[Decimal | int | float],
    change: Decimal | int | float,
) -> tuple[list[int], Decimal]:
    """Exact redistribution of leftover cash via bounded-knapsack dynamic programming.

    This is a drop-in, more powerful alternative to :func:`redistribute_change`.
    The greedy heuristic in :func:`redistribute_change` commits to the most
    underweight asset first and can strand cash whenever the first-pick asset's
    price does not evenly divide the leftover; this function instead enumerates
    every integer combination of extra shares via dynamic programming and picks
    the one that spends the most money while respecting an additional balance
    constraint that depends on ``only_buy``.

    Two modes, same DP:
        * ``only_buy=True``  -- Restrict the candidate set to assets that are
          strictly *underweight* relative to their desired allocation.  This
          preserves the buy-only promise "never increase the weight of an
          already-overweight asset", even during the redistribution phase.
          Among combinations that spend the same amount, the tiebreaker
          prefers those that concentrate on the most underweight assets.

        * ``only_buy=False`` -- Any asset already scheduled for purchase
          (``buy_quantities[i] > 0``) is a candidate.  The algorithm maximises
          spent cash without a balance filter, because any minor overshoot can
          be corrected by selling on the next rebalance cycle.  The tiebreaker
          is still applied so the output is deterministic.

    Problem formulation:
        Variables:
            x_i in Z >= 0            -- extra shares bought for asset i.
            p_i                      -- price of asset i, in scaled integer units.
            c                        -- change in the same scaled units.
            w_i = desired_i - current_i  (tiebreaker weight).
            E                        -- eligibility set (see below).

        Primary objective: maximise   S(x) = sum(p_i * x_i)      subject to S(x) <= c.
        Tiebreaker:        maximise   T(x) = sum(w_i * x_i)      among ties on S.

        Eligibility set:
            E = { i : buy_quantities[i] > 0 }                          always,
            E = E and { i : current_i < desired_i }          if only_buy=True.

    Dynamic programming (forward table of size c+1):
        dp_spent[k]   = max scaled units spendable with capacity k.
        dp_tie[k]     = best tiebreaker score achieved at that spent amount.
        parent[k]     = last item placed to reach dp_spent[k] (-1 = "copied
                        from k-1", no item placed).

        Transition for k = 1 .. c:
            Start from the "carry forward" option (dp_spent[k-1], dp_tie[k-1], -1).
            For every candidate i in E with p_i <= k:
                cand = (dp_spent[k - p_i] + p_i, dp_tie[k - p_i] + w_i)
                replace the running best if strictly greater under (spent, tie)
                lexicographic order.

        Reconstruction:
            Walk parent backwards from k = c to 0: when parent[k] != -1 we
            placed that item and jump to k - p_{parent[k]}; otherwise we jump
            to k - 1.

    Complexity:
        Time  O(n * c),   space O(c),   where c = change_units and n = |E|.

    Safety cap:
        If the scaled change exceeds :data:`MAX_CENTS` the function executes
        a fallback and delegates to the greedy :func:`redistribute_change`.
        This prevents pathological memory/time usage on very large leftover
        amounts (the realistic DCA leftover is at most a few hundred euros).

    Decimal/scaled-unit conversion:
        The integer scale preserves at least two decimal places and as much
        quote precision as the safety cap permits. Prices are rounded up at
        that scale so the selected combination cannot overspend exact cash.

    Args:
        only_buy: Selects the eligibility policy (see above).
        buy_quantities: Whole share counts already scheduled for each asset.
        ticker_prices: Exact current price per share for each asset.
        current_percentages: Current portfolio weight of each asset (%).
        desired_percentages: Target portfolio weight of each asset (%).
        change: Leftover cash to redistribute, in portfolio currency units.

    Returns:
        A tuple ``(updated_buy_quantities, remaining_change)``.  The remaining
        change is ``change - sum_of_extra_shares * price`` (currency units).
        When no extra shares can be allocated the original inputs are returned
        unchanged.

    See Also:
        :func:`redistribute_change`: the original O(n log n) greedy heuristic.
    """
    n = len(buy_quantities)
    ticker_prices_d = _decimals(ticker_prices)
    current_percentages_d = _decimals(current_percentages)
    desired_percentages_d = _decimals(desired_percentages)
    change_d = as_decimal(change)

    if change_d <= _ZERO:
        return list(buy_quantities), change_d

    eligible = [
        i
        for i in range(n)
        if buy_quantities[i] > 0
        and (
            not only_buy
            or current_percentages_d[i] < desired_percentages_d[i]
        )
    ]
    if not eligible:
        return list(buy_quantities), change_d

    scale_places = max(
        2,
        *(_decimal_places(ticker_prices_d[i]) for i in eligible),
    )
    scale = Decimal(10) ** scale_places
    while scale_places > 2 and int(change_d * scale) > MAX_CENTS:
        scale_places -= 1
        scale /= 10
    change_units = int(change_d * scale)
    prices_units = {
        i: p
        for i in eligible
        if 0 < (p := int((ticker_prices_d[i] * scale).to_integral_value(
            rounding=ROUND_CEILING,
        ))) <= change_units
    }
    candidates = list(prices_units)
    if not candidates:
        return list(buy_quantities), change_d

    # Safety cap: very large leftovers silently fall back to the cheap
    # greedy pass to avoid O(n * change_units) memory/time blowups.
    if change_units > MAX_CENTS:
        return redistribute_change(
            buy_quantities, ticker_prices_d,
            current_percentages_d, desired_percentages_d, change_d,
        )

    tie_score = {
        i: desired_percentages_d[i] - current_percentages_d[i]
        for i in candidates
    }

    # --- Dynamic programming: lexicographic max over (spent, tiebreaker) ----
    size     = change_units + 1
    dp_spent = [0] * size
    dp_tie   = [_ZERO] * size
    parent   = [-1] * size  # -1 = "carried forward from capacity k-1".

    for k in range(1, size):
        best_spent = dp_spent[k - 1]
        best_tie   = dp_tie[k - 1]
        best_item  = -1

        for i in candidates:
            p = prices_units[i]
            if p > k:
                continue
            cand_spent = dp_spent[k - p] + p
            cand_tie   = dp_tie[k - p] + tie_score[i]
            # Lexicographic comparison: (spent, tie) strictly greater.
            if (
                cand_spent > best_spent
                or (cand_spent == best_spent and cand_tie > best_tie)
            ):
                best_spent = cand_spent
                best_tie   = cand_tie
                best_item  = i

        dp_spent[k] = best_spent
        dp_tie[k]   = best_tie
        parent[k]   = best_item

    # --- Backtracking: reconstruct per-asset extra-share counts --------------
    extra = [0] * n
    k = change_units
    while k > 0:
        item = parent[k]
        if item == -1:
            # No item placed at capacity k: move one scaled unit down.
            k -= 1
        else:
            extra[item] += 1
            k -= prices_units[item]

    # Recompute from exact Decimal prices so sub-minor quote precision survives.
    updated = [
        quantity + extra_shares
        for quantity, extra_shares in zip(buy_quantities, extra)
    ]
    remaining = change_d - sum(extra[i] * ticker_prices_d[i] for i in candidates)

    return updated, remaining
