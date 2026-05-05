<script lang="ts">
  import type { RebalanceResponse, Settings } from '../types';
  import AssetResult from './AssetResult.svelte';

  export let result: RebalanceResponse | null;
  export let settings: Settings;

  $: totalAllocated = result
    ? result.results.reduce((s, r) => s + r.allocated, 0)
    : 0;

  let copied = false;
  function copyJson() {
    if (!result) return;
    navigator.clipboard.writeText(JSON.stringify(result, null, 2))
      .then(() => { copied = true; setTimeout(() => { copied = false; }, 1800); })
      .catch(() => {});
  }
</script>

<div class="panel result-panel" id="results">
  <div class="panel-head">
    <span class="panel-title">Result</span>
    {#if result}
      <div class="results-badges">
        {#if settings.onlyBuy}<span class="solver-badge">Only buy</span>{/if}
        {#if settings.optimalRedistribute}<span class="solver-badge">Knapsack DP</span>{/if}
        <button type="button" class="add-btn" style="font-size:0.75rem" on:click={copyJson}>
          {copied ? 'Copied' : 'Copy JSON'}
        </button>
      </div>
    {/if}
  </div>

  <div class="panel-body" style="padding:0.625rem 0.875rem 1rem">
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
