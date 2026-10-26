<script lang="ts">
  import type { AssetResultOut } from '../types';
  import { formatShares } from '../util';
  import { t } from '../i18n';

  export let asset: AssetResultOut;

  $: side = asset.buy > 0 ? 'buy' : asset.buy < 0 ? 'sell' : 'hold';
</script>

<tr>
  <td class="side {side}">{$t(`results.${side}`)}</td>
  <td class="num qty" class:muted={side === 'hold'}>{formatShares(Math.abs(asset.buy))}</td>
  <td class="ticker">{asset.ticker}</td>
  <td class="num weight">
    <span>{asset.current_percentage.toFixed(1)}%</span> → <span>{asset.desired_percentage.toFixed(1)}%</span>
  </td>
  <td class="num">{asset.allocated.toFixed(2)}</td>
</tr>

<style>
  .side { font-weight: 600; }
  .side.buy { color: var(--green-ink); }
  .side.sell { color: var(--red); }
  .side.hold { color: var(--ink-3); font-weight: 400; }
  .qty { font-weight: 600; }
  .qty.muted { color: var(--ink-3); font-weight: 400; }
  .ticker {
    font-family: var(--mono);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .weight { color: var(--ink-2); }
  .weight span { white-space: nowrap; }
</style>
