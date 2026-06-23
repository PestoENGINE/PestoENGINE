<script lang="ts">
  import type { Asset, UiErrorItem } from '../types';
  import AssetRow from './AssetRow.svelte';
  import PercentageIndicator from './PercentageIndicator.svelte';
  import { createEventDispatcher } from 'svelte';
  import { percentagesSumTo100 } from '../util';
  import { t } from '../i18n';

  export let assets: Asset[];
  export let loading: boolean;

  const dispatch = createEventDispatcher<{
    removeAsset: string;
    updateAsset: { id: string; patch: Partial<Asset> };
    run: void;
  }>();

  function buildValidationItems(list: Asset[], sum: number): UiErrorItem[] {
    const items: UiErrorItem[] = [];
    if (list.length === 0) return items;
    if (!percentagesSumTo100(sum)) {
      items.push({ key: 'portfolio.validation.percentageSum', params: { total: Number(sum.toFixed(2)) } });
    }

    list.forEach((asset, index) => {
      const n = index + 1;
      if (!asset.ticker.trim()) items.push({ key: 'portfolio.validation.tickerRequired', params: { n } });
      if (!Number.isFinite(asset.desiredPercentage) || asset.desiredPercentage < 0 || asset.desiredPercentage > 100) {
        items.push({ key: 'portfolio.validation.percentageRange', params: { n } });
      }
      if (!Number.isFinite(asset.shares) || asset.shares < 0) items.push({ key: 'portfolio.validation.sharesNegative', params: { n } });
      if (!Number.isFinite(asset.fees) || asset.fees < 0) items.push({ key: 'portfolio.validation.feeNegative', params: { n } });
      if (asset.percentageFee && asset.fees > 100) items.push({ key: 'portfolio.validation.feeCap', params: { n } });
    });

    return items;
  }

  $: percentageSum = assets.reduce((s, a) => s + (a.desiredPercentage || 0), 0);
  $: validationItems = buildValidationItems(assets, percentageSum);
  $: canRun = assets.length > 0 && validationItems.length === 0 && !loading;
</script>

<PercentageIndicator sum={percentageSum} />

{#if assets.length === 0}
  <div class="assets-empty" role="status">
    {$t('portfolio.empty')}
  </div>
{:else}
  <table class="asset-table">
    <colgroup>
      <col class="asset-col-ticker" />
      <col class="asset-col-target" />
      <col class="asset-col-shares" />
      <col class="asset-col-fee" />
      <col class="asset-col-actions" />
    </colgroup>
    <thead>
      <tr>
        <th>{$t('portfolio.colTicker')}</th>
        <th>{$t('portfolio.colTarget')}</th>
        <th>{$t('portfolio.colShares')}</th>
        <th>{$t('portfolio.colFee')}</th>
        <th><span class="sr-only">{$t('portfolio.colActions')}</span></th>
      </tr>
    </thead>
    <tbody>
      {#each assets as asset (asset.id)}
        <AssetRow
          {asset}
          on:update={e => dispatch('updateAsset', { id: asset.id, patch: e.detail })}
          on:remove={() => dispatch('removeAsset', asset.id)}
        />
      {/each}
    </tbody>
  </table>
{/if}

{#if validationItems.length > 0}
  <div id="portfolio-validation" class="validation-box" role="status" aria-live="polite">
    <div class="validation-title">{$t('portfolio.validation.title')}</div>
    <ul>
      {#each validationItems.slice(0, 4) as item}
        <li>{$t(item.key, item.params)}</li>
      {/each}
      {#if validationItems.length > 4}
        <li>{$t('portfolio.validation.more', { n: validationItems.length - 4 })}</li>
      {/if}
    </ul>
  </div>
{/if}

<button
  type="button"
  class="run-btn"
  on:click={() => dispatch('run')}
  disabled={!canRun}
  aria-busy={loading}
  aria-describedby={validationItems.length > 0 ? 'portfolio-validation' : undefined}
>
  {#if loading}<span class="spinner" aria-hidden="true"></span>{/if}
  <span>{loading ? $t('portfolio.calculating') : $t('portfolio.calculate')}</span>
</button>

<style>
  .assets-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 9rem;
    border: 1px dashed var(--border);
    border-radius: var(--r);
    background: color-mix(in srgb, var(--surface) 80%, var(--bg));
    font-size: 0.875rem;
    color: var(--text-3);
    text-align: center;
    padding: 1rem;
  }

  .validation-box {
    border: 1px solid var(--error-border);
    border-radius: var(--r);
    background: var(--error-bg);
    color: var(--error);
    padding: 0.7rem 0.85rem;
    margin: 0.1rem 0 0.75rem;
    font-size: 0.8125rem;
  }
  .validation-title { font-weight: 700; margin-bottom: 0.25rem; }
  .validation-box ul { list-style: disc; padding-left: 1rem; }
  .validation-box li + li { margin-top: 0.15rem; }

  .run-btn {
    width: 100%;
    background: var(--teal);
    color: #fff;
    border: none;
    border-radius: var(--r);
    padding: 0.7rem;
    font-family: var(--sans);
    font-size: 0.9375rem;
    font-weight: 600;
    cursor: pointer;
    margin-top: auto;
    transition: background 0.15s, opacity 0.15s;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    min-height: 2.65rem;
  }
  .run-btn:hover:not(:disabled) { background: var(--teal-hover); }
  :global(html.dark) .run-btn { color: #062526; }
  .run-btn:disabled { opacity: 0.45; cursor: not-allowed; }
  .spinner {
    width: 0.95rem;
    height: 0.95rem;
    border: 2px solid rgba(255,255,255,0.45);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.75s linear infinite;
  }
  :global(html.dark) .spinner {
    border-color: rgba(6,37,38,0.35);
    border-top-color: #062526;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
