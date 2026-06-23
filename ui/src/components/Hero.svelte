<script lang="ts">
  import { t } from '../i18n';
</script>

<div class="hero">
  <div class="hero-bg-text" aria-hidden="true"></div>
  <div class="hero-inner">
    <div class="hero-kicker">{$t('hero.kicker')}</div>
    <h1 class="hero-headline">{$t('hero.headlineLine1')}<br>{$t('hero.headlineLine2')}</h1>
    <p class="hero-sub">{$t('hero.sub')}</p>
  </div>
</div>

<style>
  .hero {
    background: var(--hero-bg);
    padding: clamp(2rem, 4vw, 2.75rem) clamp(1rem, 4vw, 2rem);
    border-bottom: 1px solid var(--hero-border);
    position: relative;
    overflow: hidden;
  }
  .hero-bg-text {
    position: absolute;
    right: -0.5rem;
    top: 50%;
    transform: translateY(-50%);
    font-family: var(--mono);
    font-size: clamp(4rem, 10vw, 8rem);
    font-weight: 600;
    color: rgba(255,255,255,0.03);
    letter-spacing: -0.02em;
    pointer-events: none;
    user-select: none;
    line-height: 1.1;
  }
  .hero-bg-text::before {
    content: 'VAGF\A VWCE\A SWDA';
    white-space: pre;
  }
  :global(html.dark) .hero-bg-text { color: rgba(53,200,207,0.08); }
  .hero-inner { max-width: 700px; position: relative; }
  .hero-kicker {
    font-family: var(--mono);
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--teal-on-dark);
    margin-bottom: 1rem;
  }
  .hero-headline {
    font-size: clamp(1.5rem, 4vw, 2rem);
    font-weight: 500;
    line-height: 1.2;
    color: var(--hero-text);
    margin-bottom: 1rem;
    letter-spacing: -0.02em;
  }
  .hero-sub {
    font-size: clamp(0.9375rem, 2vw, 1.0625rem);
    color: var(--hero-sub);
    line-height: 1.6;
    max-width: 560px;
    margin: 0;
  }
</style>
