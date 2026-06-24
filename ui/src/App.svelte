<script lang="ts">
  import { onMount, tick } from 'svelte';
  import type { Asset, Settings, RebalanceResponse, UiError } from './types';
  import {
    loadSettings, loadAssets, loadDarkMode,
    saveSettings, saveAssets, saveDarkMode,
    DEFAULT_SETTINGS,
  } from './storage';
  import { t, tx } from './i18n';

  import Header from './components/Header.svelte';
  import Hero from './components/Hero.svelte';
  import GlobalSettings from './components/GlobalSettings.svelte';
  import PortfolioEditor from './components/PortfolioEditor.svelte';
  import ResultsPanel from './components/ResultsPanel.svelte';
  import TrustRail from './components/TrustRail.svelte';
  import HowItWorks from './components/HowItWorks.svelte';
  import AlgoSection from './components/AlgoSection.svelte';
  import OssSection from './components/OssSection.svelte';

  import { uuid } from './util';
  import { runRebalance as apiRunRebalance } from './api';
  import { parsePortfolio, buildExport } from './portfolio-io';

  let settings: Settings = DEFAULT_SETTINGS;
  let assets: Asset[] = [];
  let lastResult: RebalanceResponse | null = null;
  let resultSettings: Settings = DEFAULT_SETTINGS;
  let error: UiError | null = null;
  let loading = false;
  let dark = false;

  let fileInput: HTMLInputElement;

  // Keep the document title in sync with the active language.
  $: document.title = $t('meta.title');

  onMount(() => {
    settings = loadSettings();
    assets = loadAssets();
    dark = loadDarkMode();
    document.documentElement.classList.toggle('dark', dark);
  });

  function updateSettings(patch: Partial<Settings>) {
    settings = { ...settings, ...patch };
    saveSettings(settings);
  }

  function addAsset() {
    const id = uuid();
    assets = [...assets, { id, ticker: '', provider: null, desiredPercentage: 0, shares: 0, fees: 0, percentageFee: false }];
    saveAssets(assets);
  }

  function removeAsset(id: string) {
    assets = assets.filter(a => a.id !== id);
    saveAssets(assets);
  }

  function updateAsset(id: string, patch: Partial<Asset>) {
    assets = assets.map(a => a.id === id ? { ...a, ...patch } : a);
    saveAssets(assets);
  }

  async function runRebalance() {
    loading = true;
    // Don't clear error/result up front: that unmounts the error box and the
    // results panel for the duration of the request, which on a fast response
    // is a visible flash + layout jump. Update state only once the outcome is
    // known so a re-click just updates the message in place.
    try {
      const r = await apiRunRebalance(settings, assets);
      if (r.ok) {
        error = null;
        resultSettings = { ...settings };
        lastResult = r.data;
        await tick();
        document.getElementById('results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else {
        error = r.error;
        lastResult = null;
      }
    } catch {
      error = { kind: 'key', key: 'errors.requestFailed' };
      lastResult = null;
    } finally {
      loading = false;
    }
  }

  function handleExport() {
    const payload = buildExport(settings, assets);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pesto-engine-portfolio-${payload.exportedAt.slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleImportRequest() {
    fileInput.value = '';
    fileInput.click();
  }

  function handleToggleDark() {
    dark = !dark;
    document.documentElement.classList.toggle('dark', dark);
    saveDarkMode(dark);
  }

  function handleFileChange(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => applyImport(ev.target?.result as string);
    reader.readAsText(file);
  }

  function applyImport(text: string) {
    const result = parsePortfolio(text);
    if (!result.ok) {
      error = result.error;
      return;
    }

    const note = result.sumWarning ? tx('import.sumNote') : '';
    if (!confirm(tx('import.confirm', { note }))) return;

    settings = result.settings;
    assets = result.assets;
    lastResult = null;
    error = null;
    saveSettings(settings);
    saveAssets(assets);
  }
</script>

<a class="skip-link" href="#main">{$t('nav.skipToMain')}</a>

<input
  bind:this={fileInput}
  type="file"
  accept=".json"
  class="hidden"
  on:change={handleFileChange}
  aria-hidden="true"
/>

<Header
  exportDisabled={assets.length === 0}
  {dark}
  on:requestImport={handleImportRequest}
  on:requestExport={handleExport}
  on:toggleDark={handleToggleDark}
/>

<main id="main" tabindex="-1">
  <Hero />

  <div class="tool-section">
    {#if error}
      <div class="error-box" role="alert">
        {#if error.kind === 'validation'}
          {error.items.map((i) => $t(i.key, i.params)).join(' · ')}
        {:else if error.kind === 'key'}
          {$t(error.key, error.params)}
        {:else}
          {error.text}
        {/if}
      </div>
    {/if}

    <div class="tool-grid">

      <div class="panel">
        <div class="panel-head">
          <span class="panel-title">{$t('panel.settings')}</span>
        </div>
        <div class="panel-body">
          <GlobalSettings
            increment={settings.increment}
            onlyBuy={settings.onlyBuy}
            optimalRedistribute={settings.optimalRedistribute}
            fractionalShares={settings.fractionalShares}
            on:update={e => updateSettings(e.detail)}
          />
        </div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="panel-title">{$t('panel.assets')}</span>
          <button type="button" class="add-asset-btn" on:click={addAsset}>{$t('assets.add')}</button>
        </div>
        <div class="panel-body tight">
          <PortfolioEditor
            {assets}
            {loading}
            on:removeAsset={e => removeAsset(e.detail)}
            on:updateAsset={e => updateAsset(e.detail.id, e.detail.patch)}
            on:run={runRebalance}
          />
        </div>
      </div>

      <ResultsPanel result={lastResult} settings={resultSettings} />

    </div>
  </div>

  <TrustRail />
  <HowItWorks />
  <AlgoSection />
  <OssSection />
</main>

<footer>
  <span>{$t('footer.brand')}</span>
  <div class="footer-links">
    <a href="https://github.com/PestoENGINE/PestoENGINE" target="_blank" rel="noopener noreferrer">{$t('footer.github')}</a>
    <span class="footer-sep">·</span>
    <span>{$t('footer.license')}</span>
    <span class="footer-sep">·</span>
    <span>{$t('footer.noAnalytics')}</span>
  </div>
</footer>

<style>
  .skip-link {
    position: fixed;
    top: 0.75rem;
    left: 0.75rem;
    z-index: 1000;
    transform: translateY(-150%);
    opacity: 0;
    pointer-events: none;
    background: var(--surface);
    border: 1px solid var(--teal);
    border-radius: var(--r);
    color: var(--teal);
    padding: 0.45rem 0.7rem;
    font-size: 0.875rem;
    font-weight: 600;
    box-shadow: 0 8px 20px rgba(0,0,0,0.18);
    transition: transform 0.15s, opacity 0.15s;
  }
  .skip-link:focus-visible {
    transform: translateY(0);
    opacity: 1;
    pointer-events: auto;
  }
  .skip-link:focus:not(:focus-visible) { transform: translateY(-150%); opacity: 0; }
  main:focus { outline: none; }

  .add-asset-btn {
    font-size: 0.75rem;
    color: var(--teal);
    border: 1px solid color-mix(in srgb, var(--teal) 35%, transparent);
    border-radius: var(--r);
    padding: 0.2rem 0.55rem;
    white-space: nowrap;
    transition: border-color 0.15s, background 0.15s;
  }
  .add-asset-btn:hover { border-color: var(--teal); background: var(--teal-light); }

  .tool-section {
    padding: clamp(1rem, 3vw, 1.5rem) clamp(1rem, 4vw, 2rem);
    max-width: 1000px;
    margin: 0 auto;
  }
  .tool-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
    gap: 1rem;
    align-items: stretch;
  }
  @media (max-width: 700px) {
    .tool-grid { grid-template-columns: 1fr; }
  }

  .error-box {
    background: var(--error-bg);
    border: 1px solid var(--error-border);
    border-radius: var(--r);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    color: var(--error);
  }
  .tool-section > .error-box { margin-bottom: 1rem; }

  footer {
    background: var(--hero-bg);
    border-top: 1px solid var(--hero-border);
    padding: 1.25rem clamp(1rem, 4vw, 2rem);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  footer span {
    font-family: var(--mono);
    font-size: 0.6875rem;
    color: var(--hero-sub);
  }
  .footer-links {
    display: flex;
    gap: 1.25rem;
    align-items: center;
  }
  footer a {
    font-size: 0.6875rem;
    color: rgba(240,237,232,0.62);
  }
  footer a:hover { color: var(--teal-on-dark); }
  .footer-sep { color: rgba(240,237,232,0.25); }
  @media (max-width: 560px) {
    footer { align-items: flex-start; }
    .footer-links { gap: 0.75rem; flex-wrap: wrap; }
  }
</style>
