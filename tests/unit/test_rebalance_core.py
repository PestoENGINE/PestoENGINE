"""Unit tests for the rebalance module."""

import unittest

from app.rebalance import (
    calculate_rebalance,
    redistribute_change,
    redistribute_change_optimal,
)
from app.rebalance.rebalance import MAX_CENTS


class TestCalculateRebalance(unittest.TestCase):
    """Tests for calculate_rebalance()."""

    # Valid inputs

    def test_standard_allow_sell(self):
        """Full rebalance (allow sell) produces correct signed amounts."""
        self.assertEqual(
            calculate_rebalance(False, 100, [0, 40, 100, 100], [60, 20, 10, 10]),
            [204.0, 28.0, -66.0, -66.0],
        )

    def test_standard_only_buy(self):
        """Only-buy mode distributes the increment proportionally to positive rebalance gaps.

        Post-increment total = 340.
        Gaps: A = 340*0.60-0 = +204, B = 340*0.20-40 = +28, C = -66, D = -66.
        Total positive gap S+ = 232.
        A receives 100 * 204/232 ≈ 87.93; B receives 100 * 28/232 ≈ 12.07.
        C and D have negative gaps and receive 0 (overweight relative to new total).
        Values are compared after {:.2f} formatting to match display precision.
        """
        result = calculate_rebalance(True, 100, [0, 40, 100, 100], [60, 20, 10, 10])
        self.assertEqual(
            [f"{v:.2f}" for v in result],
            ["87.93", "12.07", "0.00", "0.00"],
        )

    def test_zero_increment_allow_sell(self):
        """Zero increment with allow-sell shows pure rebalance deltas."""
        self.assertEqual(
            calculate_rebalance(False, 0, [0, 0, 100, 100], [60, 20, 10, 10]),
            [120.0, 40.0, -80.0, -80.0],
        )

    def test_zero_increment_only_buy(self):
        """Zero increment with only-buy results in all zeros (nothing to distribute)."""
        self.assertEqual(
            calculate_rebalance(True, 0, [0, 0, 100, 100], [60, 20, 10, 10]),
            [0.0, 0.0, 0.0, 0.0],
        )

    def test_perfectly_balanced_portfolio(self):
        """A perfectly balanced portfolio with an increment produces clean amounts."""
        # 50/50 allocation, equal values: increment should split 50/50.
        result = calculate_rebalance(True, 200, [500, 500], [50, 50])
        self.assertEqual(result, [100.0, 100.0])

    def test_single_asset(self):
        """A single-asset portfolio receives the entire increment."""
        self.assertEqual(calculate_rebalance(True, 500, [1000], [100]), [500.0])
        self.assertEqual(calculate_rebalance(False, 500, [1000], [100]), [500.0])



class TestRedistributeChange(unittest.TestCase):
    """Tests for redistribute_change()."""

    def test_change_goes_to_most_underweight_asset(self):
        """Change is allocated to the most underweight eligible asset first."""
        # Asset 0: 10% current vs 60% desired -> most underweight.
        # Asset 1: 90% current vs 40% desired -> overweight.
        buy_quantities = [1, 1]
        ticker_prices = [100.0, 500.0]
        current_pcts = [10.0, 90.0]
        desired_pcts = [60.0, 40.0]
        change = 250.0  # enough for 2 extra shares of asset 0 (2 * 100 = 200)

        updated, remaining = redistribute_change(
            buy_quantities, ticker_prices, current_pcts, desired_pcts, change
        )

        self.assertEqual(updated[0], 3.0)   # 1 original + 2 from change
        self.assertEqual(updated[1], 1.0)   # unchanged
        self.assertEqual(remaining, 50.0)   # 250 - 200 = 50

    def test_no_change_returns_unchanged(self):
        """Zero change leaves all buy quantities unchanged."""
        buy_quantities = [2, 1]
        ticker_prices = [100.0, 200.0]
        current_pcts = [50.0, 50.0]
        desired_pcts = [60.0, 40.0]

        updated, remaining = redistribute_change(
            buy_quantities, ticker_prices, current_pcts, desired_pcts, 0.0
        )

        self.assertEqual(updated, [2.0, 1.0])
        self.assertEqual(remaining, 0.0)

    def test_zero_buy_asset_is_skipped(self):
        """Assets with buy == 0 are skipped even if change could cover their price."""
        # Asset 0 is most underweight but has buy=0 and must be skipped.
        buy_quantities = [0, 1]
        ticker_prices = [50.0, 200.0]
        current_pcts = [80.0, 20.0]
        desired_pcts = [40.0, 60.0]
        change = 100.0  # enough for 2 shares of asset 0, but 0 shares of asset 1

        updated, remaining = redistribute_change(
            buy_quantities, ticker_prices, current_pcts, desired_pcts, change
        )

        self.assertEqual(updated[0], 0.0)    # skipped despite being underweight
        self.assertEqual(remaining, 100.0)   # change unspent

    def test_change_smaller_than_any_price_stays_unallocated(self):
        """Change too small to buy even one share remains as leftover."""
        buy_quantities = [1, 1]
        ticker_prices = [500.0, 300.0]
        current_pcts = [30.0, 70.0]
        desired_pcts = [70.0, 30.0]
        change = 10.0  # cannot afford a single share of either asset

        updated, remaining = redistribute_change(
            buy_quantities, ticker_prices, current_pcts, desired_pcts, change
        )

        self.assertEqual(updated, [1.0, 1.0])
        self.assertEqual(remaining, 10.0)

    def test_change_distributed_across_multiple_assets(self):
        """After exhausting one asset, remaining change moves to the next eligible one."""
        # Asset 0: price=100, most underweight. Asset 1: price=150, less underweight.
        # change=250 -> 2 shares of asset 0 (200), 0 shares of asset 1 (50 < 150).
        buy_quantities = [1, 1]
        ticker_prices = [100.0, 150.0]
        current_pcts = [20.0, 80.0]
        desired_pcts = [70.0, 30.0]
        change = 250.0

        updated, remaining = redistribute_change(
            buy_quantities, ticker_prices, current_pcts, desired_pcts, change
        )

        self.assertEqual(updated[0], 3.0)   # 1 + 2
        self.assertEqual(updated[1], 1.0)   # 50 < 150, nothing extra
        self.assertEqual(remaining, 50.0)

    def test_docstring_step_by_step_example(self):
        """Verifies the two-asset example from the formal algorithm docstring.

        Setup (from the greedy knapsack description):
            Asset A: price=10, current=20%, desired=50%, initial_qty=1
            Asset B: price=20, current=30%, desired=50%, initial_qty=1
            change = 50

        Step 1 – priorities:
            k_A = 20 / (50 + 0.01) = 0.39996...
            k_B = 30 / (50 + 0.01) = 0.59988...
            Order: A first (lower k_A → more underweight)

        Step 3 – A processed first:
            x_A = floor(50 / 10) = 5  →  remaining = 50 - 50 = 0

        Step 3 – B processed next:
            remaining = 0  →  x_B = floor(0 / 20) = 0

        Step 4 – Result: A=6, B=1, remaining=0.
        """
        buy_quantities = [1, 1]
        ticker_prices = [10.0, 20.0]
        current_pcts = [20.0, 30.0]
        desired_pcts = [50.0, 50.0]
        change = 50.0

        updated, remaining = redistribute_change(
            buy_quantities, ticker_prices, current_pcts, desired_pcts, change
        )

        self.assertEqual(updated[0], 6.0)   # 1 original + 5 from change
        self.assertEqual(updated[1], 1.0)   # change exhausted after A
        self.assertEqual(remaining, 0.0)


class TestFeeEdgeCases(unittest.TestCase):
    """Tests that verify the fee-subtraction contract.

    These tests document the expected behaviour so that anyone reading rebalance.py
    understands that max(0, r - fee) must be applied before converting currency
    amounts to share quantities.
    """

    def test_only_buy_all_overweight(self):
        """When all assets are overweight, only_buy produces all zeros."""
        result = calculate_rebalance(True, 0, [600, 400], [60, 40])
        self.assertEqual(result, [0.0, 0.0])

    def test_only_buy_single_underweight_asset_gets_full_increment(self):
        """A single underweight asset in only_buy mode receives the full increment."""
        # Asset 0 is overweight, asset 1 is strongly underweight.
        result = calculate_rebalance(True, 100, [900, 0], [50, 50])
        self.assertEqual(result[0], 0.0)
        self.assertAlmostEqual(result[1], 100.0, places=2)


# ---------------------------------------------------------------------------
# redistribute_change_optimal() - bounded-knapsack DP
# ---------------------------------------------------------------------------


class TestRedistributeChangeOptimalBuyOnly(unittest.TestCase):
    """Tests for redistribute_change_optimal(only_buy=True).

    In buy-only mode the function restricts the candidate set to STRICTLY
    underweight assets (current % < desired %), so no share purchase ever
    pushes an already-overweight asset further above its target.
    """

    # ----- stranded-cash edge cases the greedy heuristic misses -----

    def test_edge_case_A_greedy_strands_cash(self):
        """change=100, prices=[60, 45] with both assets underweight.

        Greedy buys 1xA (60) then floor(40/45)=0 -> remaining=40.
        Optimal finds 2xB (90) -> remaining=10.
        """
        updated, remaining = redistribute_change_optimal(
            only_buy=True,
            buy_quantities=[1, 1],
            ticker_prices=[60.0, 45.0],
            current_percentages=[30.0, 30.0],
            desired_percentages=[50.0, 50.0],
            change=100.0,
        )
        self.assertEqual(updated, [1, 3])
        self.assertAlmostEqual(remaining, 10.0, places=2)

    def test_edge_case_B_greedy_strands_cash(self):
        """change=250, prices=[200, 80] with both assets underweight.

        Greedy: 1xA (200), floor(50/80)=0 -> remaining=50.
        Optimal: 3xB (240) -> remaining=10.
        """
        updated, remaining = redistribute_change_optimal(
            only_buy=True,
            buy_quantities=[1, 1],
            ticker_prices=[200.0, 80.0],
            current_percentages=[30.0, 30.0],
            desired_percentages=[50.0, 50.0],
            change=250.0,
        )
        self.assertEqual(updated, [1, 4])
        self.assertAlmostEqual(remaining, 10.0, places=2)

    def test_edge_case_C_greedy_strands_cash(self):
        """change=270, prices=[100, 90] with both assets underweight.

        Greedy (A first, more underweight): 2xA (200), floor(70/90)=0 -> remaining=70.
        Optimal: 0xA + 3xB (270) -> remaining=0.
        """
        updated, remaining = redistribute_change_optimal(
            only_buy=True,
            buy_quantities=[1, 1],
            ticker_prices=[100.0, 90.0],
            current_percentages=[30.0, 30.0],
            desired_percentages=[50.0, 50.0],
            change=270.0,
        )
        self.assertEqual(updated, [1, 4])
        self.assertAlmostEqual(remaining, 0.0, places=2)

    # ----- balance-preservation tests (strict underweight filter) -----

    def test_overweight_asset_is_never_bought(self):
        """Strict filter: overweight asset with buy>0 must not receive shares.

        Pure knapsack would pick 2xA=100 (max cash). Buy-only mode refuses
        because A is already overweight and redistributes the change onto
        the underweight asset B, leaving leftover cash instead.
        """
        updated, remaining = redistribute_change_optimal(
            only_buy=True,
            buy_quantities=[1, 1],
            ticker_prices=[50.0, 40.0],
            current_percentages=[70.0, 30.0],
            desired_percentages=[40.0, 60.0],  # A overweight, B underweight
            change=100.0,
        )
        self.assertEqual(updated[0], 1)           # A unchanged (overweight)
        self.assertEqual(updated[1], 3)           # B: +2 shares (2x40=80)
        self.assertAlmostEqual(remaining, 20.0, places=2)

    def test_no_strictly_underweight_assets_is_noop(self):
        """When no asset is strictly underweight, nothing is bought."""
        updated, remaining = redistribute_change_optimal(
            only_buy=True,
            buy_quantities=[1, 1],
            ticker_prices=[50.0, 40.0],
            current_percentages=[60.0, 40.0],
            desired_percentages=[60.0, 40.0],  # exactly at target, not strict <
            change=100.0,
        )
        self.assertEqual(updated, [1, 1])
        self.assertAlmostEqual(remaining, 100.0, places=2)

    # ----- tiebreaker -----

    def test_tiebreaker_prefers_more_underweight_asset(self):
        """Among combinations with equal max-spent, prefer the most underweight.

        Setup: three equal-price assets.  A and B underweight but A is deeper
        below target; C overweight (excluded).  With change=100 (exactly 2
        shares), the DP can pick 2xA, 1xA+1xB or 2xB -- all spend 100.
        Tiebreaker score = sum((desired-current) * x):
            2xA = 2*30 = 60 (best)
            1A+1B = 30+10 = 40
            2xB = 2*10 = 20
        """
        updated, remaining = redistribute_change_optimal(
            only_buy=True,
            buy_quantities=[1, 1, 1],
            ticker_prices=[50.0, 50.0, 50.0],
            current_percentages=[10.0, 20.0, 70.0],
            desired_percentages=[40.0, 30.0, 30.0],
            change=100.0,
        )
        self.assertEqual(updated, [3, 1, 1])
        self.assertAlmostEqual(remaining, 0.0, places=2)

    # ----- eligibility (buy==0) -----

    def test_zero_buy_asset_is_skipped(self):
        """Base eligibility: assets with buy==0 are never touched.

        A is underweight and cheap but buy=0 -> must stay at 0.
        B receives the full redistribution.
        """
        updated, remaining = redistribute_change_optimal(
            only_buy=True,
            buy_quantities=[0, 1],
            ticker_prices=[50.0, 80.0],
            current_percentages=[80.0, 20.0],
            desired_percentages=[40.0, 60.0],
            change=100.0,
        )
        self.assertEqual(updated[0], 0)
        self.assertEqual(updated[1], 2)  # 1 + floor(100/80)=1
        self.assertAlmostEqual(remaining, 20.0, places=2)

    # ----- parity with greedy when greedy already hits optimum -----

    def test_parity_with_greedy_when_greedy_is_optimal(self):
        """Reuses the greedy docstring example; both algorithms must agree.

        prices=[10, 20] exactly divide change=50 at asset A, so greedy
        already reaches spent=50 and remaining=0.  Optimal must produce
        the same result.
        """
        buy = [1, 1]
        prices = [10.0, 20.0]
        cur = [20.0, 30.0]
        des = [50.0, 50.0]
        change = 50.0

        greedy_updated, greedy_remaining = redistribute_change(
            buy, prices, cur, des, change,
        )
        optimal_updated, optimal_remaining = redistribute_change_optimal(
            True, buy, prices, cur, des, change,
        )

        self.assertEqual(optimal_updated, [6, 1])
        self.assertAlmostEqual(optimal_remaining, 0.0, places=2)
        # And they match exactly.
        self.assertEqual(optimal_updated, greedy_updated)
        self.assertAlmostEqual(optimal_remaining, greedy_remaining, places=2)

    # ----- safety cap fallback -----

    def test_fallback_to_greedy_above_safety_cap(self):
        """change_cents > MAX_CENTS silently delegates to the greedy path.

        With such a large change the DP would allocate ~1 MB+ of RAM per
        array; the function short-circuits to :func:`redistribute_change`
        instead.  The two outputs must therefore coincide.
        """
        change = (MAX_CENTS / 100.0) + 5000.0  # 5000 above the cap
        buy = [1, 1]
        prices = [60.0, 45.0]
        cur = [20.0, 30.0]
        des = [50.0, 50.0]

        optimal_updated, optimal_remaining = redistribute_change_optimal(
            True, buy, prices, cur, des, change,
        )
        greedy_updated, greedy_remaining = redistribute_change(
            buy, prices, cur, des, change,
        )
        self.assertEqual(optimal_updated, greedy_updated)
        self.assertAlmostEqual(optimal_remaining, greedy_remaining, places=2)


class TestRedistributeChangeOptimalRebalance(unittest.TestCase):
    """Tests for redistribute_change_optimal(only_buy=False).

    In allow-sell mode the strict-underweight filter is NOT applied: the DP
    maximises spent cash over every asset with buy>0, because any overshoot
    can be corrected by selling on the next rebalance cycle.
    """

    def test_overweight_asset_can_be_bought_for_max_spend(self):
        """No balance filter: pure knapsack buys overweight if it maximises cash.

        Same setup as test_overweight_asset_is_never_bought() but with
        only_buy=False.  Now 2xA=100 beats 2xB=80: A gains shares even though
        it was already overweight.
        """
        updated, remaining = redistribute_change_optimal(
            only_buy=False,
            buy_quantities=[1, 1],
            ticker_prices=[50.0, 40.0],
            current_percentages=[70.0, 30.0],
            desired_percentages=[40.0, 60.0],
            change=100.0,
        )
        self.assertEqual(updated, [3, 1])
        self.assertAlmostEqual(remaining, 0.0, places=2)

    def test_tiebreaker_gives_deterministic_output(self):
        """Equal spent combinations resolve via (desired - current) tiebreak.

        Three combinations spend exactly 100: 2xA, 2xB, 1A+1B.
        Scores: 2xA=+80 (A underweight), 2xB=-80 (B overweight), 1A+1B=0.
        Tiebreaker picks 2xA.
        """
        updated, remaining = redistribute_change_optimal(
            only_buy=False,
            buy_quantities=[1, 1],
            ticker_prices=[50.0, 50.0],
            current_percentages=[10.0, 90.0],
            desired_percentages=[50.0, 50.0],
            change=100.0,
        )
        self.assertEqual(updated, [3, 1])
        self.assertAlmostEqual(remaining, 0.0, places=2)

    def test_stranded_cash_edge_case_in_rebalance_mode(self):
        """The same Edge Case A also benefits in rebalance mode."""
        updated, remaining = redistribute_change_optimal(
            only_buy=False,
            buy_quantities=[1, 1],
            ticker_prices=[60.0, 45.0],
            current_percentages=[30.0, 30.0],
            desired_percentages=[50.0, 50.0],
            change=100.0,
        )
        # 2xB = 90 still wins over 1xA = 60 (max spent).
        self.assertEqual(updated, [1, 3])
        self.assertAlmostEqual(remaining, 10.0, places=2)

    def test_zero_buy_asset_is_skipped_in_rebalance_mode(self):
        """Even in rebalance mode, buy==0 assets stay at 0."""
        updated, remaining = redistribute_change_optimal(
            only_buy=False,
            buy_quantities=[0, 1],
            ticker_prices=[50.0, 80.0],
            current_percentages=[80.0, 20.0],
            desired_percentages=[40.0, 60.0],
            change=100.0,
        )
        self.assertEqual(updated[0], 0)
        self.assertEqual(updated[1], 2)
        self.assertAlmostEqual(remaining, 20.0, places=2)


class TestRedistributeChangeOptimalShared(unittest.TestCase):
    """Edge cases that must behave identically in both modes."""

    def test_zero_change_is_noop(self):
        for mode in (True, False):
            with self.subTest(only_buy=mode):
                updated, remaining = redistribute_change_optimal(
                    mode, [1, 1], [50.0, 40.0],
                    [20.0, 30.0], [50.0, 50.0], 0.0,
                )
                self.assertEqual(updated, [1, 1])
                self.assertEqual(remaining, 0.0)

    def test_negative_change_is_noop(self):
        """A negative leftover (e.g. rounding with fees) returns unchanged."""
        for mode in (True, False):
            with self.subTest(only_buy=mode):
                updated, remaining = redistribute_change_optimal(
                    mode, [1, 1], [50.0, 40.0],
                    [20.0, 30.0], [50.0, 50.0], -5.0,
                )
                self.assertEqual(updated, [1, 1])
                self.assertEqual(remaining, -5.0)

    def test_no_eligible_assets_is_noop(self):
        """All buy==0 -> nothing to redistribute."""
        for mode in (True, False):
            with self.subTest(only_buy=mode):
                updated, remaining = redistribute_change_optimal(
                    mode, [0, 0], [50.0, 40.0],
                    [20.0, 30.0], [50.0, 50.0], 100.0,
                )
                self.assertEqual(updated, [0, 0])
                self.assertAlmostEqual(remaining, 100.0, places=2)

    def test_change_smaller_than_any_price_is_noop(self):
        """When no candidate price fits, change is returned unchanged."""
        for mode in (True, False):
            with self.subTest(only_buy=mode):
                updated, remaining = redistribute_change_optimal(
                    mode, [1, 1], [500.0, 300.0],
                    [30.0, 30.0], [50.0, 50.0], 10.0,
                )
                self.assertEqual(updated, [1, 1])
                self.assertAlmostEqual(remaining, 10.0, places=2)

    def test_empty_inputs_is_noop(self):
        """Zero-length portfolios short-circuit gracefully."""
        for mode in (True, False):
            with self.subTest(only_buy=mode):
                updated, remaining = redistribute_change_optimal(
                    mode, [], [], [], [], 100.0,
                )
                self.assertEqual(updated, [])
                self.assertAlmostEqual(remaining, 100.0, places=2)

    def test_zero_priced_assets_are_skipped(self):
        """Defensive: a price of 0 must not trigger an infinite DP or crash."""
        for mode in (True, False):
            with self.subTest(only_buy=mode):
                updated, remaining = redistribute_change_optimal(
                    mode, [1, 1], [0.0, 0.0],
                    [30.0, 30.0], [50.0, 50.0], 100.0,
                )
                self.assertEqual(updated, [1, 1])
                self.assertAlmostEqual(remaining, 100.0, places=2)


if __name__ == "__main__":
    unittest.main()
