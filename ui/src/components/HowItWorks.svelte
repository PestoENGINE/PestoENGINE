<script lang="ts">
  import { t } from '../i18n';

  const steps = [1, 2, 3] as const;

  const requestSample = `{
  "increment": 1000,
  "only_buy": true,
  "optimal_redistribute": true,
  "assets": [
    {
      "ticker": "VWCE.DE",
      "desired_percentage": 60,
      "shares": 10,
      "fees": 3.95
    }
  ],
  "base_currency": "EUR"
}`;
</script>

<section class="page-section">
  <div class="container">
    <h2 class="section-title">{$t('howItWorks.kicker')}</h2>
    <p class="section-lead">{$t('howItWorks.headline')}</p>

    <div class="page-columns how-grid">
      <ol class="steps">
        {#each steps as step}
          <li class="step">
            <h3 class="step-title">{$t(`howItWorks.step${step}Title`)}</h3>
            <p class="step-text">{$t(`howItWorks.step${step}Text`)}</p>
          </li>
        {/each}
      </ol>

      <figure class="code-block">
        <figcaption>{$t('howItWorks.codeHeader')}</figcaption>
        <pre><code>{requestSample}</code></pre>
      </figure>
    </div>
  </div>
</section>

<style>
  .how-grid { margin-top: 2rem; }

  .steps {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    padding-left: 1.5rem;
    list-style: decimal;
  }
  .step::marker {
    font-family: var(--mono);
    font-weight: 600;
    color: var(--green-ink);
  }
  .step-title { font-size: 1rem; font-weight: 600; }
  .step-text { margin-top: 0.25rem; font-size: 0.9375rem; line-height: 1.6; color: var(--ink-2); }
</style>
