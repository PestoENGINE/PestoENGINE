<script lang="ts">
  import type { Asset, UiErrorItem } from '../types';
  import AssetRow from './AssetRow.svelte';
  import { createEventDispatcher } from 'svelte';
  import { percentagesSumTo100 } from '../util';
  import { t } from '../i18n';

  export let assets: Asset[];
  export let loading: boolean;
  export let baseCurrency: string;

  const dispatch = createEventDispatcher<{
    addAsset: void;
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
  $: sumValid = percentagesSumTo100(percentageSum);
  $: validationItems = buildValidationItems(assets, percentageSum);
  $: canRun = assets.length > 0 && validationItems.length === 0 && !loading;
</script>

<table class="sheet holdings-sheet" aria-label={$t('panel.assets')}>
  <colgroup>
    <col class="col-ticker" />
    <col class="col-target" />
    <col class="col-shares" />
    <col class="col-fee" />
    <col class="col-unit" />
    <col class="col-actions" />
  </colgroup>
  <thead>
    <tr>
      <th scope="col">{$t('portfolio.colTicker')}</th>
      <th scope="col" class="num">{$t('portfolio.colTarget')}</th>
      <th scope="col" class="num">{$t('portfolio.colShares')}</th>
      <th scope="col" class="num">{$t('portfolio.colFee')}</th>
      <th scope="col"><span class="sr-only">{$t('portfolio.colFeeUnit')}</span></th>
      <th scope="col"><span class="sr-only">{$t('portfolio.colActions')}</span></th>
    </tr>
  </thead>
  <tbody>
    {#if assets.length === 0}
      <tr>
        <td colspan="6" class="empty-cell">
          <div role="status">{$t('portfolio.empty')}</div>
        </td>
      </tr>
    {:else}
      {#each assets as asset (asset.id)}
        <AssetRow
          {asset}
          {baseCurrency}
          on:update={e => dispatch('updateAsset', { id: asset.id, patch: e.detail })}
          on:remove={() => dispatch('removeAsset', asset.id)}
        />
      {/each}
    {/if}
  </tbody>
  {#if assets.length > 0}
    <tfoot>
      <tr>
        <th scope="row">{$t('percentage.total')}</th>
        <td class="num total" class:ok={sumValid} class:bad={!sumValid}>{percentageSum.toFixed(2)}</td>
        <td></td>
        <td></td>
        <td></td>
        <td></td>
      </tr>
    </tfoot>
  {/if}
</table>

{#if validationItems.length > 0}
  <div id="portfolio-validation" class="notice validation" role="status" aria-live="polite">
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

<div class="sheet-actions">
  <button type="button" class="btn" on:click={() => dispatch('addAsset')}>{$t('assets.add')}</button>
  <button
    type="button"
    class="btn btn-primary run-btn"
    on:click={() => dispatch('run')}
    disabled={!canRun}
    aria-busy={loading}
    aria-describedby={validationItems.length > 0 ? 'portfolio-validation' : undefined}
  >
    {#if loading}<span class="spinner" aria-hidden="true"></span>{/if}
    <span>{loading ? $t('portfolio.calculating') : $t('portfolio.calculate')}</span>
  </button>
</div>

<style>
  /* Fixed layout: every column but the ticker has a set width, so the ticker
     column absorbs whatever is left instead of the browser spreading it. */
  .holdings-sheet { table-layout: fixed; }
  .col-target,
  .col-shares { width: 17%; }
  .col-fee { width: 19%; }
  .col-unit { width: 3.75rem; }
  .col-actions { width: 2.75rem; }

  .empty-cell {
    height: 6rem;
    text-align: center;
    color: var(--ink-3);
  }
  .total.ok { color: var(--green-ink); }
  .total.bad { color: var(--red); }

  .validation { margin-top: 0.75rem; }
  .validation-title { font-weight: 600; margin-bottom: 0.2rem; }
  .validation ul { list-style: disc; padding-left: 1.1rem; }
  .validation li + li { margin-top: 0.15rem; }

  .sheet-actions {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    margin-top: 0.875rem;
  }
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    height: 2.75rem;
    padding: 0 1.25rem;
    border: 1px solid var(--rule-strong);
    border-radius: var(--r);
    background: var(--paper);
    color: var(--ink);
    font-size: 0.9375rem;
    font-weight: 500;
    white-space: nowrap;
  }
  .btn:hover:not(:disabled) { border-color: var(--frame); }
  .btn-primary {
    border-color: var(--frame);
    background: var(--green);
    color: var(--on-green);
    font-weight: 600;
  }
  .btn-primary:hover:not(:disabled) { background: var(--green-hover); }
  .btn-primary:disabled {
    border-color: var(--rule-strong);
    background: var(--paper-2);
    color: var(--ink-3);
    cursor: not-allowed;
  }
  .run-btn { min-width: 14rem; }
  .run-btn[aria-busy='true'] {
    border-color: var(--frame);
    background: var(--green);
    color: var(--on-green);
    cursor: progress;
  }
  .spinner {
    width: 0.9rem;
    height: 0.9rem;
    border: 2px solid color-mix(in srgb, currentColor 30%, transparent);
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.75s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  @media (max-width: 600px) {
    .col-target,
    .col-shares,
    .col-fee { width: 19%; }
    .col-unit { width: 2.75rem; }
    .col-actions { width: 2.25rem; }
  }

  /* Phones: each asset takes two lines on one four-track grid. Line 1 is the
     ticker plus the remove button, line 2 is target / shares / fee / unit; the
     last track is shared by the remove button and the fee unit, so the
     vertical rules line up from the header down to the total. Inputs go to
     16px, below which iOS Safari zooms the page on focus. */
  @media (max-width: 520px) {
    .holdings-sheet,
    .holdings-sheet thead,
    .holdings-sheet tbody,
    .holdings-sheet tfoot { display: block; }
    .holdings-sheet colgroup { display: none; }
    .holdings-sheet :global(tr) {
      display: grid;
      grid-template-columns: minmax(4.125rem, 0.8fr) minmax(0, 1.3fr) minmax(4.125rem, 0.9fr) 2.75rem;
    }
    .holdings-sheet :global(tr > *) {
      grid-row: 2;
      border-bottom: 0;
      /* Grid items ignore vertical-align: centre single-line text by line height. */
      line-height: 2.5rem;
      white-space: nowrap;
    }
    .holdings-sheet :global(tr > :first-child) {
      grid-row: 1;
      grid-column: 1 / 4;
      border-bottom: 1px solid var(--rule);
    }
    .holdings-sheet :global(tr > :nth-child(6)) {
      grid-row: 1;
      grid-column: 4;
      border-right: 0;
      border-bottom: 1px solid var(--rule);
    }
    .holdings-sheet :global(tr > :nth-child(5)) { border-right: 0; }
    .holdings-sheet :global(thead tr) { border-bottom: 1px solid var(--rule-strong); }
    .holdings-sheet :global(tbody tr + tr) { border-top: 1px solid var(--rule-strong); }
    .holdings-sheet :global(.cell-input) { font-size: 16px; }

    .holdings-sheet :global(tbody tr > .empty-cell) {
      grid-column: 1 / -1;
      line-height: 1.5;
      white-space: normal;
      border: 0;
      align-content: center;
    }

    .holdings-sheet :global(tfoot tr) {
      display: flex;
      border-top: 1px solid var(--rule-strong);
    }
    .holdings-sheet tfoot :global(tr > th:first-child) { flex: 1; border: 0; }
    .holdings-sheet tfoot :global(td) { border-right: 0; }
    .holdings-sheet tfoot :global(td:empty) { display: none; }
  }

  @media (max-width: 480px) {
    .sheet-actions { flex-direction: column; }
    .run-btn { min-width: 0; }
  }
</style>
