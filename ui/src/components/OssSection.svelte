<script lang="ts">
  import { t } from '../i18n';
</script>

<div class="oss-section">
  <div class="oss-inner">
    <div>
      <div class="oss-kicker">{$t('oss.kicker')}</div>
      <h2 class="oss-headline">{$t('oss.headlineLine1')}<br>{$t('oss.headlineLine2')}</h2>
      <p class="oss-text">{$t('oss.text1')}</p>
      <p class="oss-text">{$t('oss.text2')}</p>
      <div class="oss-links">
        <a class="oss-link" href="https://github.com/PestoENGINE/PestoENGINE" target="_blank" rel="noopener noreferrer">{$t('oss.linkStar')}</a>
        <a class="oss-link" href="https://github.com/PestoENGINE/PestoENGINE/blob/master/app/rebalance/rebalance.py" target="_blank" rel="noopener noreferrer">{$t('oss.linkAlgo')}</a>
        <a class="oss-link" href="https://github.com/PestoENGINE/PestoENGINE/blob/master/CONTRIBUTING.md" target="_blank" rel="noopener noreferrer">{$t('oss.linkContrib')}</a>
      </div>
    </div>
    <div>
      <div class="quickstart">
        <div class="qs-header">{$t('oss.quickStart')}</div>
        <div class="qs-body">
          <span class="qs-line"><span class="qs-prompt">$</span><span class="qs-cmd">docker run -d \</span></span>
          <span class="qs-line"><span class="qs-cmd">{'   '}--name pestoengine \</span></span>
          <span class="qs-line"><span class="qs-cmd">{'   '}-p 8000:8000 \</span></span>
          <span class="qs-line"><span class="qs-cmd">{'   '}ghcr.io/pestoengine/pestoengine:latest</span></span>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .oss-section {
    background: var(--hero-bg);
    padding: clamp(3rem, 6vw, 5rem) clamp(1rem, 4vw, 2rem);
    border-top: 1px solid var(--hero-border);
  }
  .oss-inner {
    max-width: 960px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: clamp(2rem, 5vw, 3.5rem);
    align-items: start;
  }
  .oss-inner > * { min-width: 0; }
  @media (max-width: 720px) { .oss-inner { grid-template-columns: 1fr; } }
  .oss-kicker {
    font-family: var(--mono);
    font-size: 0.6875rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--teal-on-dark);
    margin-bottom: 0.75rem;
  }
  .oss-headline {
    font-size: clamp(1.125rem, 2.5vw, 1.375rem);
    font-weight: 500;
    color: var(--hero-text);
    margin-bottom: 1.125rem;
    line-height: 1.3;
  }
  .oss-text { font-size: 0.9375rem; color: var(--hero-sub); line-height: 1.65; margin-bottom: 1.125rem; }
  .oss-links { display: flex; gap: 0.625rem; flex-wrap: wrap; margin-top: 1.5rem; }
  .oss-link {
    font-size: 0.875rem;
    color: var(--teal-on-dark);
    border: 1px solid color-mix(in srgb, var(--teal-on-dark) 45%, transparent);
    border-radius: var(--r);
    padding: 0.4rem 0.875rem;
    text-decoration: none;
  }
  .oss-link:hover { border-color: var(--teal-on-dark); background: rgba(53,200,207,0.12); }

  .quickstart {
    width: 100%;
    max-width: 100%;
    min-width: 0;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: var(--r);
    font-family: var(--mono);
    font-size: 0.8125rem;
    line-height: 1.9;
    color: rgba(240,237,232,0.7);
    overflow: hidden;
  }
  .qs-header {
    padding: 0.5rem 1.125rem;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    font-size: 0.6875rem;
    color: rgba(240,237,232,0.68);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .qs-body { padding: 1rem 1.125rem; min-width: 0; }
  .qs-prompt { color: rgba(1,180,188,0.5); display: inline-block; width: 1.25rem; user-select: none; }
  .qs-cmd { color: #7dd3d6; white-space: pre-wrap; overflow-wrap: anywhere; word-break: break-word; }
  .qs-line { display: block; padding-left: 1.25rem; min-width: 0; }
  .qs-line:has(.qs-prompt) { padding-left: 0; }
  @media (max-width: 393px) {
    .quickstart { font-size: 0.75rem; }
    .qs-header { padding: 0.45rem 0.875rem; }
    .qs-body { padding: 0.85rem 0.875rem; }
  }
  @media (max-width: 360px) {
    .oss-section { padding-left: 0.75rem; padding-right: 0.75rem; }
    .quickstart { font-size: 0.625rem; }
    .qs-header { padding: 0.45rem 0.75rem; }
    .qs-body { padding: 0.75rem; }
    .qs-line { padding-left: 1rem; }
  }
</style>
