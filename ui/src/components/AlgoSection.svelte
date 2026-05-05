<div style="border-top:1px solid var(--border)">
  <div class="content-section">
    <div class="section-kicker">The algorithm</div>
    <h2 class="section-headline">Three modes. Named, documented, auditable.</h2>

    <div style="overflow-x:auto">
      <table class="algo-table">
        <thead>
          <tr>
            <th>Mode</th>
            <th>Complexity</th>
            <th>Cash deployment</th>
            <th>Use when</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Greedy</td>
            <td>O(n log n)</td>
            <td>Good. Allocates by largest allocation gap first. May leave small amounts undeployed.</td>
            <td>Speed matters; some leftover tolerance is acceptable.</td>
          </tr>
          <tr>
            <td>Knapsack DP</td>
            <td>O(n × W)</td>
            <td>Maximum. Treats share purchases as items in a bounded knapsack. Minimises leftover change.</td>
            <td>Cash efficiency matters; minimises leftover change.</td>
          </tr>
          <tr>
            <td>Buy-only</td>
            <td>O(n)</td>
            <td>No new cash deployed. Ranks assets by allocation deficit and returns buy quantities to close the gap using existing cash only.</td>
            <td>Rebalancing without adding capital; set <span class="inline-code">only_buy: true</span>.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p style="font-size:0.9375rem;color:var(--text-2);margin-top:1.5rem;line-height:1.65">
      The algorithm is not proprietary. The source is in <span class="inline-code">app/rebalance/rebalance.py</span>. Every formula is readable and every result is verifiable by hand.
    </p>
  </div>
</div>
