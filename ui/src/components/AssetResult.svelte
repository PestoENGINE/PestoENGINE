<script lang="ts">
  import type { AssetResultOut } from '../types';
  import { formatShares } from '../util';

  export let asset: AssetResultOut;

  $: muted = asset.buy === 0;
  $: driftWidth = asset.desired_percentage > 0
    ? Math.min((asset.current_percentage / asset.desired_percentage) * 100, 100)
    : 0;
</script>

<div class="result-row result-grid">
  <div class="result-ticker">{asset.ticker}</div>
  <div class="result-buy" class:muted>{formatShares(asset.buy)}</div>
  <div class="result-meta">
    <div class="result-drift">
      <div class="delta-bar">
        <div class="delta-fill" style="width:{driftWidth}%"></div>
      </div>
      <span class="delta-text">{asset.current_percentage.toFixed(1)}% → {asset.desired_percentage.toFixed(1)}%</span>
    </div>
    <div class="result-allocated">{asset.allocated.toFixed(2)}</div>
  </div>
</div>

<style>
  .result-row {
    align-items: center;
    padding: 0.625rem 0;
    border-top: 1px solid var(--border);
    min-width: 0;
  }
  .result-row:first-of-type { border-top: none; }
  .result-ticker {
    font-family: var(--mono);
    font-weight: 600;
    font-size: 0.875rem;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .result-buy {
    color: var(--teal);
    font-family: var(--mono);
    font-weight: 600;
    font-size: 0.875rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .result-buy.muted { color: var(--text-3); }
  .result-meta {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.625rem;
    align-items: center;
    min-width: 0;
  }
  .result-drift {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    min-width: 0;
  }
  .delta-bar {
    width: 30px;
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    flex: 0 0 30px;
  }
  .delta-fill { height: 100%; background: var(--teal); border-radius: 2px; }
  .delta-text {
    font-size: 0.6875rem;
    color: var(--text-3);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }
  .result-allocated {
    font-family: var(--mono);
    font-size: 0.875rem;
    font-variant-numeric: tabular-nums;
    color: var(--text-2);
    text-align: right;
    white-space: nowrap;
  }
  @media (max-width: 700px) {
    .result-meta { grid-template-columns: 1fr; gap: 0.2rem; align-items: start; }
    .result-allocated { text-align: left; }
    .delta-bar { width: 24px; flex-basis: 24px; }
  }
  @media (max-width: 480px) {
    .result-buy { font-size: 0.75rem; }
  }
</style>
