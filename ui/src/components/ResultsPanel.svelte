<script lang="ts">
  import type { RebalanceResponse, Settings } from '../types';
  import AssetResult from './AssetResult.svelte';
  import { t } from '../i18n';

  export let result: RebalanceResponse | null;
  export let settings: Settings;

  $: modes = [
    ...(settings.onlyBuy ? [$t('results.badgeOnlyBuy')] : []),
    ...(settings.optimalRedistribute ? [$t('results.badgeKnapsack')] : []),
  ];
</script>

<section class="orders" id="results" aria-labelledby="orders-title">
  <div class="orders-head">
    <h2 id="orders-title" class="orders-title">{$t('results.title')}</h2>
    {#if result && modes.length > 0}
      <span class="orders-mode">{modes.join(', ')}</span>
    {/if}
  </div>

  {#if result}
    <table class="sheet orders-sheet">
      <thead>
        <tr>
          <th scope="col">{$t('results.colOrder')}</th>
          <th scope="col" class="num">{$t('results.colShares')}</th>
          <th scope="col">{$t('results.colTicker')}</th>
          <th scope="col" class="num">{$t('results.colWeight')}</th>
          <th scope="col" class="num">{$t('results.colAmount')} ({settings.baseCurrency})</th>
        </tr>
      </thead>
      <tbody>
        {#each result.results as asset (asset.id)}
          <AssetResult {asset} />
        {/each}
      </tbody>
      <tfoot>
        <tr>
          <th scope="row" colspan="4">{$t('results.allocated')}</th>
          <td class="num">{result.results.reduce((sum, asset) => sum + asset.allocated, 0).toFixed(2)}</td>
        </tr>
        <tr>
          <th scope="row" colspan="4">{$t('results.totalFees')}</th>
          <td class="num">{result.total_fees.toFixed(2)}</td>
        </tr>
        <tr>
          <th scope="row" colspan="4">{$t('results.change')}</th>
          <td class="num">{result.change.toFixed(2)}</td>
        </tr>
      </tfoot>
    </table>
  {:else}
    <div class="orders-empty">{$t('results.empty')}</div>
  {/if}
</section>

<style>
  .orders {
    margin-top: 2.5rem;
    padding-bottom: clamp(3rem, 6vw, 4.5rem);
    scroll-margin-top: calc(var(--nav-height) + 1rem);
  }
  .orders-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.25rem 1rem;
    margin-bottom: 0.625rem;
  }
  .orders-title { font-size: 1.125rem; font-weight: 600; }
  .orders-mode { font-size: 0.875rem; color: var(--ink-3); }

  .orders-sheet tfoot th { font-weight: 500; color: var(--ink-2); }
  .orders-sheet tfoot tr:last-child > * { color: var(--ink); font-weight: 600; }

  .orders-empty {
    display: grid;
    place-items: center;
    min-height: 6rem;
    padding: 1rem;
    border: 1px dashed var(--rule-strong);
    color: var(--ink-3);
    font-size: 0.9375rem;
    text-align: center;
  }

  @media (max-width: 600px) {
    .orders-sheet { font-size: 0.8125rem; }
  }

  /* Phones: each order reads as two lines, like an order slip:
     "VWCE.DE ... 529.60" over "Buy 4 ... 58.4% → 60.0%". */
  @media (max-width: 520px) {
    .orders-sheet,
    .orders-sheet thead,
    .orders-sheet tbody,
    .orders-sheet tfoot { display: block; }
    .orders-sheet :global(thead tr),
    .orders-sheet :global(tbody tr) {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto;
      grid-template-areas:
        "ticker ticker amount"
        "side qty weight";
    }
    /* Grid items ignore vertical-align: centre single-line cells by line height. */
    .orders-sheet :global(tr > *) {
      height: 2rem;
      line-height: 2rem;
      white-space: nowrap;
      border-right: 0;
      border-bottom: 0;
    }
    .orders-sheet :global(tfoot tr > *) { height: 2.5rem; line-height: 2.5rem; }
    .orders-sheet :global(tr > :nth-child(1)) { grid-area: side; padding-right: 0.25rem; }
    .orders-sheet :global(tr > :nth-child(2)) { grid-area: qty; text-align: left; padding-left: 0.25rem; }
    .orders-sheet :global(tr > :nth-child(3)) { grid-area: ticker; }
    .orders-sheet :global(tr > :nth-child(4)) { grid-area: weight; }
    .orders-sheet :global(tr > :nth-child(5)) { grid-area: amount; }
    .orders-sheet :global(thead tr) { border-bottom: 1px solid var(--rule-strong); }
    .orders-sheet :global(tbody tr) { padding-block: 0.25rem; }
    .orders-sheet :global(tbody tr + tr) { border-top: 1px solid var(--rule); }

    .orders-sheet :global(tfoot tr) {
      display: flex;
      justify-content: space-between;
      border-top: 1px solid var(--rule);
    }
    .orders-sheet :global(tfoot tr:first-child) { border-top-color: var(--rule-strong); }
    .orders-sheet :global(tfoot th) { flex: 1; }
  }
</style>
