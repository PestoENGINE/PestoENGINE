<script lang="ts">
  import type { AssetResultOut } from '../types';

  export let asset: AssetResultOut;

  $: muted = asset.buy === 0;
  $: driftWidth = asset.desired_percentage > 0
    ? Math.min((asset.current_percentage / asset.desired_percentage) * 100, 100)
    : 0;
</script>

<div class="result-row">
  <div class="result-ticker">{asset.ticker}</div>
  <div class="result-buy {muted ? 'muted' : ''}">{asset.buy}</div>
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
