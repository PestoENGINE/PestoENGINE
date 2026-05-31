<script lang="ts">
  import type { Asset } from '../types';
  import { createEventDispatcher } from 'svelte';
  import TickerAutocomplete from './TickerAutocomplete.svelte';

  export let asset: Asset;

  const dispatch = createEventDispatcher<{ update: Partial<Asset>; remove: void }>();

  function num(e: Event): number {
    return parseFloat((e.target as HTMLInputElement).value) || 0;
  }
</script>

<tr>
  <td class="ticker-cell">
    <TickerAutocomplete
      id="ticker-{asset.id}"
      value={asset.ticker}
      on:change={e => dispatch('update', { ticker: e.detail.ticker, provider: e.detail.provider })}
      cellStyle={true}
    />
  </td>
  <td>
    <input
      type="number"
      min="0"
      max="100"
      step="any"
      value={asset.desiredPercentage}
      on:input={e => dispatch('update', { desiredPercentage: num(e) })}
      class="cell-input"
      aria-label="Target percentage"
    />
  </td>
  <td>
    <input
      type="number"
      min="0"
      step="any"
      value={asset.shares}
      on:input={e => dispatch('update', { shares: num(e) })}
      class="cell-input"
      aria-label="Shares held"
    />
  </td>
  <td>
    <div class="fee-cell">
      <input
        type="number"
        min="0"
        step="any"
        value={asset.fees}
        on:input={e => dispatch('update', { fees: num(e) })}
        class="cell-input"
        aria-label="Fee"
      />
      <label class="fee-toggle" title="Percentage fee">
        <input
          type="checkbox"
          checked={asset.percentageFee}
          on:change={e => dispatch('update', { percentageFee: (e.target as HTMLInputElement).checked })}
        />
        <span class="fee-pct">%</span>
      </label>
    </div>
  </td>
  <td>
    <div class="asset-actions">
      <button
        type="button"
        class="remove-btn"
        on:click={() => dispatch('remove')}
        aria-label="Remove asset"
      >×</button>
    </div>
  </td>
</tr>
