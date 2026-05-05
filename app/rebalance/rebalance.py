"""Core functions for portfolio rebalancing calculations."""

# DP safety cap: above this change (in cents) fall back to greedy to avoid O(n*c) blowup.
MAX_CENTS: int = 1_000_000


def _redistribute_proportional_to_gap(
    values: list[float],
    percentages: list[float],
    increment: float,
) -> list[float]:
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
    total_value = sum(values) + increment
    gaps = [(total_value * p / 100.0) - v for p, v in zip(percentages, values)]

    total_positive = sum(g for g in gaps if g > 0)
    if total_positive == 0:
        return [0.0] * len(values)

    return [
        increment * (g / total_positive) if g > 0 else 0.0
        for g in gaps
    ]


def calculate_rebalance(
    only_buy: bool,
    increment: float,
    values: list[float],
    percentages: list[float],
) -> list[float]:
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
    total_value = sum(values) + increment
    return [(total_value * (p / 100.0)) - v for p, v in zip(percentages, values)]


def redistribute_change(
    buy_quantities: list[int],
    ticker_prices: list[float],
    current_percentages: list[float],
    desired_percentages: list[float],
    change: float,
) -> tuple[list[int], float]:
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
    if change <= 0:
        return list(buy_quantities), change

    # ε avoids division-by-zero; lower ratio = more underweight = higher priority.
    epsilon = 0.01
    priorities = [
        current_percentages[i] / (desired_percentages[i] + epsilon)
        for i in range(len(buy_quantities))
    ]
    sorted_indices = sorted(range(len(buy_quantities)), key=lambda i: priorities[i])

    updated = list(buy_quantities)
    remaining = change
    for i in sorted_indices:
        if updated[i] <= 0:
            continue
        x_i = int(remaining // ticker_prices[i])
        remaining -= x_i * ticker_prices[i]
        updated[i] += x_i

    return updated, remaining


def redistribute_change_optimal(
    only_buy: bool,
    buy_quantities: list[int],
    ticker_prices: list[float],
    current_percentages: list[float],
    desired_percentages: list[float],
    change: float,
) -> tuple[list[int], float]:
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
            p_i                      -- price of asset i, in cents (integer).
            c                        -- change to redistribute, in cents.
            w_i = desired_i - current_i  (tiebreaker weight).
            E                        -- eligibility set (see below).

        Primary objective: maximise   S(x) = sum(p_i * x_i)      subject to S(x) <= c.
        Tiebreaker:        maximise   T(x) = sum(w_i * x_i)      among ties on S.

        Eligibility set:
            E = { i : buy_quantities[i] > 0 }                          always,
            E = E and { i : current_i < desired_i }          if only_buy=True.

    Dynamic programming (forward table of size c+1):
        dp_spent[k]   = max cents spendable with capacity k.
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
        Time  O(n * c),   space O(c),   where c = change_cents and n = |E|.

    Safety cap:
        If ``change_cents`` exceeds :data:`MAX_CENTS` the function executes
        a fallback and delegates to the greedy :func:`redistribute_change`.
        This prevents pathological memory/time usage on very large leftover
        amounts (the realistic DCA leftover is at most a few hundred euros).

    Float/cent conversion:
        ``round(x * 100)`` converts prices and change to integer cents.
        ``round`` is required (not ``int``) because floats like ``118.42``
        are not exactly representable in binary, so ``118.42 * 100`` can
        produce ``11841.999...`` and truncation would yield a wrong cent count.
        The final remainder is computed entirely in integer cents and divided
        by 100 once at the very end to minimise floating-point drift.

    Args:
        only_buy: Selects the eligibility policy (see above).
        buy_quantities: Whole share counts already scheduled for each asset.
        ticker_prices: Current price per share for each asset, pre-rounded
            to 2 decimal places.
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

    # Fast exits: nothing to distribute, or no assets at all.
    if n == 0 or change <= 0:
        return list(buy_quantities), change

    # Base eligibility (same contract as redistribute_change): only touch
    # assets that were already scheduled for purchase in this cycle.
    eligible = [i for i in range(n) if buy_quantities[i] > 0]
    if not eligible:
        return list(buy_quantities), change

    # Stricter eligibility for only_buy mode: never push an asset further
    # above its target weight - exclude everything that is not STRICTLY
    # underweight.  This preserves the portfolio-balance guarantee promised by
    # buy-only mode even in the redistribution phase.
    if only_buy:
        eligible = [
            i for i in eligible
            if current_percentages[i] < desired_percentages[i]
        ]
        if not eligible:
            return list(buy_quantities), change

    change_cents = round(change * 100)
    prices_cents = {
        i: p
        for i in eligible
        if 0 < (p := round(ticker_prices[i] * 100)) <= change_cents
    }
    candidates = list(prices_cents.keys())
    if not candidates:
        return list(buy_quantities), change

    # Safety cap: very large leftovers silently fall back to the cheap
    # greedy pass to avoid O(n * change_cents) memory/time blowups.
    if change_cents > MAX_CENTS:
        return redistribute_change(
            buy_quantities, ticker_prices,
            current_percentages, desired_percentages, change,
        )

    tie_score = {
        i: desired_percentages[i] - current_percentages[i]
        for i in candidates
    }

    # --- Dynamic programming: lexicographic max over (spent, tiebreaker) ----
    size     = change_cents + 1
    dp_spent = [0] * size
    dp_tie   = [0.0] * size
    parent   = [-1] * size  # -1 = "carried forward from capacity k-1".

    for k in range(1, size):
        best_spent = dp_spent[k - 1]
        best_tie   = dp_tie[k - 1]
        best_item  = -1

        for i in candidates:
            p = prices_cents[i]
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
    k = change_cents
    while k > 0:
        item = parent[k]
        if item == -1:
            # No item placed at capacity k: move one cent down.
            k -= 1
        else:
            extra[item] += 1
            k -= prices_cents[item]

    # Integer-cent arithmetic avoids FP drift; single /100 at the end.
    updated = list(buy_quantities)
    spent_cents = 0
    for i in candidates:
        updated[i] += extra[i]
        spent_cents += extra[i] * prices_cents[i]

    remaining = (change_cents - spent_cents) / 100.0

    return updated, remaining
