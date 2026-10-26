<script lang="ts">
  import { t } from '../i18n';
  import TrustRail from './TrustRail.svelte';
</script>

<div class="intro">
  <h1 class="intro-title">{$t('hero.headlineLine1')}<br>{$t('hero.headlineLine2')}</h1>
  <p class="intro-sub">{$t('hero.sub')}</p>
  <TrustRail />
</div>

<style>
  .intro {
    padding: clamp(2rem, 5vw, 3rem) 0 clamp(1.5rem, 3vw, 2rem);
  }
  .intro-title {
    font-size: clamp(1.625rem, 4vw, 2.25rem);
    font-weight: 600;
    line-height: 1.15;
    letter-spacing: -0.015em;
  }
  .intro-sub {
    max-width: 38rem;
    margin-top: 0.75rem;
    font-size: 1.0625rem;
    line-height: 1.55;
    color: var(--ink-2);
  }
</style>
