<script lang="ts">
  import { t } from '../i18n';

  // These two strings embed an inline-code span. We keep the {code} marker
  // literal in the dictionary and split around it so the span stays in the
  // static markup (and keeps its scoped CSS), instead of using {@html}.
  $: buyonlyUseParts = $t('algo.buyonlyUse').split('{code}');
  $: noteParts = $t('algo.note').split('{code}');
</script>

<div class="section-divider">
  <div class="content-section">
    <div class="section-kicker">{$t('algo.kicker')}</div>
    <h2 class="section-headline">{$t('algo.headline')}</h2>

    <div class="table-scroll">
      <table class="algo-table">
        <thead>
          <tr>
            <th>{$t('algo.colMode')}</th>
            <th>{$t('algo.colComplexity')}</th>
            <th>{$t('algo.colDeployment')}</th>
            <th>{$t('algo.colUseWhen')}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{$t('algo.greedyName')}</td>
            <td>O(n log n)</td>
            <td>{$t('algo.greedyDeploy')}</td>
            <td>{$t('algo.greedyUse')}</td>
          </tr>
          <tr>
            <td>{$t('algo.knapsackName')}</td>
            <td>O(n × W)</td>
            <td>{$t('algo.knapsackDeploy')}</td>
            <td>{$t('algo.knapsackUse')}</td>
          </tr>
          <tr>
            <td>{$t('algo.buyonlyName')}</td>
            <td>O(n)</td>
            <td>{$t('algo.buyonlyDeploy')}</td>
            <td>{buyonlyUseParts[0]}<span class="inline-code">only_buy: true</span>{buyonlyUseParts[1] ?? ''}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="algo-note">
      {noteParts[0]}<span class="inline-code">app/rebalance/rebalance.py</span>{noteParts[1] ?? ''}
    </p>
  </div>
</div>

<style>
  .table-scroll { overflow-x: auto; }

  .algo-table { width: 100%; border-collapse: collapse; margin-top: 1.5rem; }
  .algo-table th {
    font-size: 0.6875rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-2);
    padding: 0.5rem 1rem 0.75rem;
    text-align: left;
    border-bottom: 2px solid var(--border);
  }
  .algo-table td {
    padding: 1rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.9375rem;
    vertical-align: top;
    line-height: 1.5;
  }
  .algo-table tr:last-child td { border-bottom: none; }
  .algo-table td:first-child { font-family: var(--mono); font-weight: 600; font-size: 0.875rem; color: var(--teal); white-space: nowrap; }
  .algo-table td:nth-child(2) { font-size: 0.875rem; color: var(--text-2); }
  .algo-table td:nth-child(3), .algo-table td:nth-child(4) { color: var(--text-2); font-size: 0.875rem; }

  .inline-code {
    font-family: var(--mono);
    font-size: 0.8125rem;
    background: var(--teal-light);
    color: var(--teal);
    padding: 0.1rem 0.35rem;
    border-radius: 2px;
  }

  .algo-note {
    font-size: 0.9375rem;
    color: var(--text-2);
    margin-top: 1.5rem;
    line-height: 1.65;
  }
</style>
