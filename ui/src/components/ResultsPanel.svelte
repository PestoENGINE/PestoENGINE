<script lang="ts">
  import type { RebalanceResponse, Settings } from '../types';
  import AssetResult from './AssetResult.svelte';

  export let result: RebalanceResponse | null;
  export let settings: Settings;

  $: totalAllocated = result
    ? result.results.reduce((s, r) => s + r.allocated, 0)
    : 0;
</script>

<div class="panel result-panel" id="results">
  <div class="panel-head">
    <span class="panel-title">Result</span>
    {#if result}
      <div class="results-badges">
        {#if settings.onlyBuy}<span class="solver-badge">Only buy</span>{/if}
        {#if settings.optimalRedistribute}<span class="solver-badge">Knapsack DP</span>{/if}
      </div>
    {/if}
  </div>

  <div class="panel-body tight-x">
    {#if result}
      <div class="result-list">
        <div class="result-list-head">
          <span>Ticker</span>
          <span>Buy</span>
          <span>Result</span>
        </div>
        {#each result.results as asset (asset.id)}
          <AssetResult {asset} />
        {/each}
      </div>

      <div class="results-summary">
        <div>
          <div class="stat-label">Allocated</div>
          <div class="stat-val">{totalAllocated.toFixed(2)}</div>
        </div>
        <div>
          <div class="stat-label">Total fees</div>
          <div class="stat-val">{result.total_fees.toFixed(2)}</div>
        </div>
        <div>
          <div class="stat-label">Change</div>
          <div class="stat-val">{result.change.toFixed(2)}</div>
        </div>
      </div>
    {:else}
      <div class="result-empty">Run the calculator to see results.</div>
    {/if}
  </div>
</div>

<style>
  .result-panel {
    grid-column: 1 / -1;
    scroll-margin-top: calc(var(--nav-height) + var(--panel-gap));
  }
  @media (max-width: 600px) {
    .result-panel { grid-column: auto; }
  }

  .solver-badge {
    font-size: 0.6875rem;
    background: var(--teal-light);
    color: var(--teal);
    border-radius: 100px;
    padding: 0.5rem 0.5rem;
    font-family: var(--mono);
    line-height: 1;
    white-space: nowrap;
  }
  .results-badges {
    display: flex;
    gap: 0.375rem;
    flex-wrap: wrap;
    justify-content: flex-end;
    min-width: 0;
  }

  .result-list { width: 100%; min-width: 0; }
  .result-list-head {
    display: grid;
    grid-template-columns: var(--result-cols);
    gap: var(--result-gap);
    padding: 0 0 0.625rem;
    font-size: 0.6875rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-3);
  }

  .results-summary {
    border-top: 1px solid var(--border);
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.5rem;
    padding: 0.875rem 0 0;
    margin-top: 0.5rem;
  }
  .stat-label {
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-3);
    margin-bottom: 0.2rem;
  }
  .stat-val {
    font-family: var(--mono);
    font-size: 1rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .result-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.875rem;
    color: var(--text-3);
  }

  @media (max-width: 480px) {
    .stat-val { font-size: 0.875rem; }
    .results-summary { gap: 0.25rem; }
  }
</style>
