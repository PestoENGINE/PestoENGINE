<script lang="ts">
  import { t } from '../i18n';

  const quickStart = `$ docker run -d \\
    --name pestoengine \\
    -p 8000:8000 \\
    ghcr.io/pestoengine/pestoengine:latest`;
</script>

<section class="page-section">
  <div class="container page-columns">
    <div>
      <h2 class="section-title">{$t('oss.kicker')}</h2>
      <p class="section-lead">{$t('oss.headlineLine1')} {$t('oss.headlineLine2')}</p>
      <p class="oss-text">{$t('oss.text1')}</p>
      <p class="oss-text">{$t('oss.text2')}</p>
      <ul class="oss-links">
        <li><a href="https://github.com/PestoENGINE/PestoENGINE" target="_blank" rel="noopener noreferrer">{$t('oss.linkStar')}</a></li>
        <li><a href="https://github.com/PestoENGINE/PestoENGINE/blob/master/app/rebalance/rebalance.py" target="_blank" rel="noopener noreferrer">{$t('oss.linkAlgo')}</a></li>
        <li><a href="https://github.com/PestoENGINE/PestoENGINE/blob/master/CONTRIBUTING.md" target="_blank" rel="noopener noreferrer">{$t('oss.linkContrib')}</a></li>
      </ul>
    </div>

    <figure class="code-block">
      <figcaption>{$t('oss.quickStart')}</figcaption>
      <pre><code>{quickStart}</code></pre>
    </figure>
  </div>
</section>

<style>
  .oss-text {
    margin-top: 1rem;
    font-size: 0.9375rem;
    line-height: 1.65;
    color: var(--ink-2);
  }
  .oss-links {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1.5rem;
    margin-top: 1.5rem;
  }
  .oss-links a {
    display: inline-block;
    padding-block: 0.25rem;
    font-size: 0.9375rem;
    font-weight: 500;
    color: var(--ink);
    text-decoration: underline;
    text-decoration-color: var(--green);
    text-decoration-thickness: 2px;
    text-underline-offset: 4px;
  }
  .oss-links a:hover { color: var(--green-ink); }
</style>
