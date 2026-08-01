<script lang="ts">
  import type { RebalanceResponse, Settings } from '../types';
  import AssetResult from './AssetResult.svelte';
  import { t } from '../i18n';

  export let result: RebalanceResponse | null;
  export let settings: Settings;
</script>

<div class="panel result-panel" id="results">
  <div class="panel-head">
    <span class="panel-title">{$t('results.title')}</span>
    {#if result}
      <div class="results-badges">
        {#if settings.onlyBuy}<span class="solver-badge">{$t('results.badgeOnlyBuy')}</span>{/if}
        {#if settings.optimalRedistribute}<span class="solver-badge">{$t('results.badgeKnapsack')}</span>{/if}
      </div>
    {/if}
  </div>

  <div class="panel-body tight-x">
    {#if result}
      <div class="result-list">
        <div class="result-list-head result-grid">
          <span>{$t('results.colTicker')}</span>
          <span>{$t('results.colBuy')}</span>
          <span>{$t('results.colResult')}</span>
        </div>
        {#each result.results as asset (asset.id)}
          <AssetResult {asset} />
        {/each}
      </div>

      <div class="results-summary">
        <div>
          <div class="stat-label">{$t('results.allocated')}</div>
          <div class="stat-val">{result.results.reduce((sum, asset) => sum + asset.allocated, 0).toFixed(2)}</div>
        </div>
        <div>
          <div class="stat-label">{$t('results.totalFees')}</div>
          <div class="stat-val">{result.total_fees.toFixed(2)}</div>
        </div>
        <div>
          <div class="stat-label">{$t('results.change')}</div>
          <div class="stat-val">{result.change.toFixed(2)}</div>
        </div>
        <div>
          <div class="stat-label">{$t('results.currency')}</div>
          <div class="stat-val">{settings.baseCurrency}</div>
        </div>
      </div>
    {:else}
      <div class="result-empty">{$t('results.empty')}</div>
    {/if}
  </div>
</div>

<style>
  .result-panel {
    grid-column: 1 / -1;
    scroll-margin-top: calc(var(--nav-height) + var(--panel-gap));
  }
  @media (max-width: 700px) {
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
    grid-template-columns: repeat(4, minmax(0, 1fr));
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
    .results-summary {
      gap: 0.75rem 0.5rem;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
