<script lang="ts">
  import type { Asset } from '../types';
  import { createEventDispatcher } from 'svelte';
  import TickerAutocomplete from './TickerAutocomplete.svelte';
  import { inputNumber, inputChecked } from '../util';

  export let asset: Asset;

  const dispatch = createEventDispatcher<{ update: Partial<Asset>; remove: void }>();
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
      on:input={e => dispatch('update', { desiredPercentage: inputNumber(e) })}
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
      on:input={e => dispatch('update', { shares: inputNumber(e) })}
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
        on:input={e => dispatch('update', { fees: inputNumber(e) })}
        class="cell-input"
        aria-label="Fee"
      />
      <label class="fee-toggle" title="Percentage fee">
        <input
          type="checkbox"
          checked={asset.percentageFee}
          on:change={e => dispatch('update', { percentageFee: inputChecked(e) })}
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

<style>
  .ticker-cell { min-width: 0; overflow: visible; position: relative; }

  .asset-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.5rem;
  }

  .fee-cell { display: flex; align-items: center; gap: 0.375rem; }
  .fee-cell .cell-input { width: 1.5rem; flex: none; }
  .fee-toggle { cursor: pointer; display: flex; align-items: center; gap: 0.2rem; }
  .fee-toggle input[type='checkbox'] { width: 12px; height: 12px; margin-top: 0; }
  .fee-pct { font-family: var(--mono); font-size: 0.6875rem; color: var(--text-3); }

  .remove-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-3);
    font-size: 0.875rem;
    padding: 0 0.25rem;
    line-height: 1;
  }
  .remove-btn:hover { color: var(--error); }
</style>
