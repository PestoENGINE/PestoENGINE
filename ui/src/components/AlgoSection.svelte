<div class="section-divider">
  <div class="content-section">
    <div class="section-kicker">The algorithm</div>
    <h2 class="section-headline">Three modes. Named, documented, auditable.</h2>

    <div class="table-scroll">
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

    <p class="algo-note">
      The algorithm is not proprietary. The source is in <span class="inline-code">app/rebalance/rebalance.py</span>. Every formula is readable and every result is verifiable by hand.
    </p>
  </div>
</div>

<style>
  .table-scroll { overflow-x: auto; }

  .algo-table { width: 100%; border-collapse: collapse; margin-top: 1.5rem; }
  .algo-table th {
    font-size: 0.6875rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-2);
    padding: 0.5rem 1rem 0.75rem;
    text-align: left;
    border-bottom: 2px solid var(--border);
  }
  .algo-table td {
    padding: 1rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.9375rem;
    vertical-align: top;
    line-height: 1.5;
  }
  .algo-table tr:last-child td { border-bottom: none; }
  .algo-table td:first-child { font-family: var(--mono); font-weight: 600; font-size: 0.875rem; color: var(--teal); white-space: nowrap; }
  .algo-table td:nth-child(2) { font-size: 0.875rem; color: var(--text-2); }
  .algo-table td:nth-child(3), .algo-table td:nth-child(4) { color: var(--text-2); font-size: 0.875rem; }

  .inline-code {
    font-family: var(--mono);
    font-size: 0.8125rem;
    background: var(--teal-light);
    color: var(--teal);
    padding: 0.1rem 0.35rem;
    border-radius: 2px;
  }

  .algo-note {
    font-size: 0.9375rem;
    color: var(--text-2);
    margin-top: 1.5rem;
    line-height: 1.65;
  }
</style>
