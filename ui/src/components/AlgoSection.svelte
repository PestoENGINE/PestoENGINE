<script lang="ts">
  import { t } from '../i18n';

  // These two strings embed an inline-code span. We keep the {code} marker
  // literal in the dictionary and split around it so the span stays in the
  // static markup (and keeps its scoped CSS), instead of using {@html}.
  $: buyonlyUseParts = $t('algo.buyonlyUse').split('{code}');
  $: noteParts = $t('algo.note').split('{code}');

  const modes = [
    { key: 'greedy', complexity: 'O(n log n)' },
    { key: 'knapsack', complexity: 'O(n × W)' },
    { key: 'buyonly', complexity: 'O(n)' },
  ] as const;
</script>

<section class="page-section">
  <div class="container">
    <h2 class="section-title">{$t('algo.kicker')}</h2>
    <p class="section-lead">{$t('algo.headline')}</p>

    <table class="sheet algo-sheet">
      <thead>
        <tr>
          <th scope="col">{$t('algo.colMode')}</th>
          <th scope="col">{$t('algo.colComplexity')}</th>
          <th scope="col">{$t('algo.colDeployment')}</th>
          <th scope="col">{$t('algo.colUseWhen')}</th>
        </tr>
      </thead>
      <tbody>
        {#each modes as mode}
          <tr>
            <th scope="row" data-label={$t('algo.colMode')}>{$t(`algo.${mode.key}Name`)}</th>
            <td data-label={$t('algo.colComplexity')} class="complexity">{mode.complexity}</td>
            <td data-label={$t('algo.colDeployment')}>{$t(`algo.${mode.key}Deploy`)}</td>
            <td data-label={$t('algo.colUseWhen')}>
              {#if mode.key === 'buyonly'}
                {buyonlyUseParts[0]}<span class="inline-code">only_buy: true</span>{buyonlyUseParts[1] ?? ''}
              {:else}
                {$t(`algo.${mode.key}Use`)}
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>

    <p class="algo-note">
      {noteParts[0]}<span class="inline-code">app/rebalance/rebalance.py</span>{noteParts[1] ?? ''}
    </p>
  </div>
</section>

<style>
  .algo-sheet { margin-top: 2rem; }
  .algo-sheet tbody th,
  .algo-sheet tbody td {
    height: auto;
    padding-block: 0.75rem;
    vertical-align: top;
    line-height: 1.55;
  }
  .algo-sheet tbody td { color: var(--ink-2); }
  .algo-sheet tbody th {
    font-family: var(--mono);
    font-weight: 600;
    white-space: nowrap;
  }
  .complexity { font-family: var(--mono); white-space: nowrap; }

  .inline-code {
    padding: 0.05rem 0.3rem;
    border: 1px solid var(--rule);
    border-radius: var(--r);
    background: var(--paper-2);
    font-family: var(--mono);
    font-size: 0.8125rem;
    color: var(--ink);
    overflow-wrap: anywhere;
  }

  .algo-note {
    max-width: 44rem;
    margin-top: 1.25rem;
    font-size: 0.9375rem;
    line-height: 1.65;
    color: var(--ink-2);
  }

  /* Narrow screens: one block per mode, each cell labelled by its column. */
  @media (max-width: 700px) {
    .algo-sheet,
    .algo-sheet tbody,
    .algo-sheet tr,
    .algo-sheet th,
    .algo-sheet td { display: block; }
    .algo-sheet thead { display: none; }
    .algo-sheet tbody th,
    .algo-sheet tbody td {
      padding: 0 0.875rem;
      border-right: 0;
      border-bottom: 0;
    }
    .algo-sheet tbody tr { padding: 0.875rem 0; border-bottom: 1px solid var(--rule); }
    .algo-sheet tbody tr:last-child { border-bottom: 0; }
    .algo-sheet tbody td { margin-top: 0.5rem; }
    .algo-sheet tbody td::before {
      content: attr(data-label);
      display: block;
      font-family: var(--sans);
      font-size: 0.75rem;
      font-weight: 500;
      color: var(--ink-3);
    }
  }
</style>
