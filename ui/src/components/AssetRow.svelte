<script lang="ts">
  import type { Asset } from '../types';
  import { createEventDispatcher } from 'svelte';
  import TickerAutocomplete from './TickerAutocomplete.svelte';
  import { inputChecked } from '../util';
  import { t } from '../i18n';

  export let asset: Asset;

  const dispatch = createEventDispatcher<{ update: Partial<Asset>; remove: void }>();

  let valueAssetId = '';
  let targetValue = '';
  let sharesValue = '';
  let feesValue = '';

  function displayNumber(value: number): string {
    return Number.isFinite(value) ? String(value) : '0';
  }

  function parseInputValue(value: string): number {
    const parsed = Number.parseFloat(value.replace(',', '.'));
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function syncLocalValues(nextAsset: Asset): void {
    valueAssetId = nextAsset.id;
    targetValue = displayNumber(nextAsset.desiredPercentage);
    sharesValue = displayNumber(nextAsset.shares);
    feesValue = displayNumber(nextAsset.fees);
  }

  function normalizeEmpty(field: 'target' | 'shares' | 'fees'): void {
    if (field === 'target' && targetValue.trim() === '') targetValue = '0';
    if (field === 'shares' && sharesValue.trim() === '') sharesValue = '0';
    if (field === 'fees' && feesValue.trim() === '') feesValue = '0';
  }

  $: if (asset.id !== valueAssetId) syncLocalValues(asset);
  $: tickerInvalid = asset.ticker.trim().length === 0;
  $: targetInvalid = !Number.isFinite(asset.desiredPercentage) || asset.desiredPercentage < 0 || asset.desiredPercentage > 100;
  $: sharesInvalid = !Number.isFinite(asset.shares) || asset.shares < 0;
  $: feeInvalid = !Number.isFinite(asset.fees) || asset.fees < 0 || (asset.percentageFee && asset.fees > 100);
</script>

<tr>
  <td class="ticker-cell" data-label={$t('portfolio.colTicker')}>
    <TickerAutocomplete
      id="ticker-{asset.id}"
      value={asset.ticker}
      on:change={e => dispatch('update', { ticker: e.detail.ticker, provider: e.detail.provider })}
      cellStyle={true}
      invalid={tickerInvalid}
    />
  </td>
  <td data-label={$t('portfolio.colTarget')}>
    <input
      type="text"
      inputmode="decimal"
      autocomplete="off"
      value={targetValue}
      on:input={e => { targetValue = (e.target as HTMLInputElement).value; dispatch('update', { desiredPercentage: parseInputValue(targetValue) }); }}
      on:blur={() => normalizeEmpty('target')}
      class="cell-input"
      aria-label={$t('assetRow.targetAria')}
      aria-invalid={targetInvalid ? 'true' : undefined}
    />
  </td>
  <td data-label={$t('portfolio.colShares')}>
    <input
      type="text"
      inputmode="decimal"
      autocomplete="off"
      value={sharesValue}
      on:input={e => { sharesValue = (e.target as HTMLInputElement).value; dispatch('update', { shares: parseInputValue(sharesValue) }); }}
      on:blur={() => normalizeEmpty('shares')}
      class="cell-input"
      aria-label={$t('assetRow.sharesAria')}
      aria-invalid={sharesInvalid ? 'true' : undefined}
    />
  </td>
  <td data-label={$t('portfolio.colFee')}>
    <div class="fee-cell">
      <input
        type="text"
        inputmode="decimal"
        autocomplete="off"
        value={feesValue}
        on:input={e => { feesValue = (e.target as HTMLInputElement).value; dispatch('update', { fees: parseInputValue(feesValue) }); }}
        on:blur={() => normalizeEmpty('fees')}
        class="cell-input"
        aria-label={$t('assetRow.feeAria')}
        aria-invalid={feeInvalid ? 'true' : undefined}
      />
      <label class="fee-toggle" title={$t('assetRow.percentageFeeTitle')}>
        <input
          type="checkbox"
          checked={asset.percentageFee}
          on:change={e => dispatch('update', { percentageFee: inputChecked(e) })}
        />
        <span class="fee-pct">%</span>
      </label>
    </div>
  </td>
  <td data-label={$t('portfolio.colActions')}>
    <div class="asset-actions">
      <button
        type="button"
        class="remove-btn"
        on:click={() => dispatch('remove')}
        aria-label={$t('assetRow.removeAria')}
        title={$t('assetRow.removeAria')}
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
  .fee-cell .cell-input { width: 3.75rem; flex: 0 0 3.75rem; }
  .fee-toggle { cursor: pointer; display: flex; align-items: center; gap: 0.2rem; }
  .fee-toggle input[type='checkbox'] { width: 12px; height: 12px; margin: 0; }
  .fee-pct { font-family: var(--mono); font-size: 0.6875rem; color: var(--text-3); }

  .remove-btn {
    width: 1.65rem;
    height: 1.65rem;
    display: grid;
    place-items: center;
    border: 1px solid transparent;
    color: var(--text-3);
    font-size: 1.15rem;
    padding: 0;
    line-height: 1;
    border-radius: 999px;
  }
  .remove-btn:hover { color: var(--error); background: var(--error-bg); border-color: var(--error-border); }
  :global(.cell-input[aria-invalid='true']) { color: var(--error); }
  @media (max-width: 700px) {
    .fee-cell .cell-input { width: 100%; flex: 1 1 auto; }
    .asset-actions { justify-content: flex-end; }
  }
</style>
