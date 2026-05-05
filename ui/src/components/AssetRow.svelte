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
  <td style="min-width:0;overflow:visible;position:relative">
    <TickerAutocomplete
      id="ticker-{asset.id}"
      value={asset.ticker}
      on:change={e => dispatch('update', { ticker: e.detail })}
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
    <div style="display:flex;align-items:center;gap:0.375rem">
      <input
        type="number"
        min="0"
        step="any"
        value={asset.fees}
        on:input={e => dispatch('update', { fees: num(e) })}
        class="cell-input"
        style="flex:1"
        aria-label="Fee"
      />
      <label style="cursor:pointer;display:flex;align-items:center;gap:0.2rem" title="Percentage fee">
        <input
          type="checkbox"
          checked={asset.percentageFee}
          on:change={e => dispatch('update', { percentageFee: (e.target as HTMLInputElement).checked })}
          style="width:12px;height:12px;margin-top:0"
        />
        <span style="font-family:var(--mono);font-size:0.6875rem;color:var(--text-3)">%</span>
      </label>
    </div>
  </td>
  <td style="text-align:right">
    <button
      type="button"
      class="remove-btn"
      on:click={() => dispatch('remove')}
      aria-label="Remove asset"
    >×</button>
  </td>
</tr>
