<script lang="ts">
  import { t } from '../i18n';

  const keys = ['trust.openSource', 'trust.noData', 'trust.selfHost', 'trust.documented'];
</script>

<p class="trust">{keys.map((k) => $t(k)).join('. ')}.</p>

<style>
  .trust {
    max-width: 46rem;
    margin-top: 0.5rem;
    font-size: 0.875rem;
    color: var(--ink-3);
  }
</style>
