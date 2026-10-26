<script lang="ts">
  import type { Asset } from '../types';
  import { createEventDispatcher } from 'svelte';
  import TickerAutocomplete from './TickerAutocomplete.svelte';
  import { t } from '../i18n';

  export let asset: Asset;
  export let baseCurrency: string;

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
  <td class="cell ticker-cell">
    <TickerAutocomplete
      id="ticker-{asset.id}"
      value={asset.ticker}
      on:change={e => dispatch('update', {
        ticker: e.detail.ticker,
        provider: e.detail.provider,
        currency: e.detail.currency,
      })}
      cellStyle={true}
      invalid={tickerInvalid}
    />
  </td>
  <td class="cell">
    <input
      type="text"
      inputmode="decimal"
      autocomplete="off"
      value={targetValue}
      on:input={e => { targetValue = (e.target as HTMLInputElement).value; dispatch('update', { desiredPercentage: parseInputValue(targetValue) }); }}
      on:blur={() => normalizeEmpty('target')}
      class="cell-input num"
      aria-label={$t('assetRow.targetAria')}
      aria-invalid={targetInvalid ? 'true' : undefined}
    />
  </td>
  <td class="cell">
    <input
      type="text"
      inputmode="decimal"
      autocomplete="off"
      value={sharesValue}
      on:input={e => { sharesValue = (e.target as HTMLInputElement).value; dispatch('update', { shares: parseInputValue(sharesValue) }); }}
      on:blur={() => normalizeEmpty('shares')}
      class="cell-input num"
      aria-label={$t('assetRow.sharesAria')}
      aria-invalid={sharesInvalid ? 'true' : undefined}
    />
  </td>
  <td class="cell">
    <input
      type="text"
      inputmode="decimal"
      autocomplete="off"
      value={feesValue}
      on:input={e => { feesValue = (e.target as HTMLInputElement).value; dispatch('update', { fees: parseInputValue(feesValue) }); }}
      on:blur={() => normalizeEmpty('fees')}
      class="cell-input num"
      aria-label={$t('assetRow.feeAria')}
      aria-invalid={feeInvalid ? 'true' : undefined}
    />
  </td>
  <td class="cell">
    <button
      type="button"
      class="fee-unit"
      aria-pressed={asset.percentageFee}
      aria-label={$t('assetRow.percentageFeeTitle')}
      title={$t('assetRow.percentageFeeTitle')}
      on:click={() => dispatch('update', { percentageFee: !asset.percentageFee })}
    >{asset.percentageFee ? '%' : baseCurrency}</button>
  </td>
  <td class="cell">
    <button
      type="button"
      class="remove-btn"
      on:click={() => dispatch('remove')}
      aria-label={$t('assetRow.removeAria')}
      title={$t('assetRow.removeAria')}
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
    </button>
  </td>
</tr>

<style>
  .ticker-cell { position: relative; }

  /* Unit of the fee: the portfolio currency (flat) or % (of the order). */
  .fee-unit {
    display: block;
    width: 100%;
    height: 2.5rem;
    background: var(--paper-2);
    font-family: var(--mono);
    font-size: 0.75rem;
    color: var(--ink-2);
  }
  .fee-unit:hover { color: var(--ink); background: var(--rule); }
  .fee-unit:focus-visible { outline-offset: -2px; }

  .remove-btn {
    display: grid;
    place-items: center;
    width: 100%;
    height: 2.5rem;
    color: var(--ink-3);
  }
  .remove-btn:hover { color: var(--red); background: var(--red-wash); }
  .remove-btn:focus-visible { outline-offset: -2px; }
</style>
