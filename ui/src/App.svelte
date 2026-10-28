<script lang="ts">
  import { onMount, tick } from 'svelte';
  import type { Asset, Settings, RebalanceEngine, RebalanceResponse, UiError } from './types';
  import {
    loadSettings, loadAssets, loadDarkMode,
    saveSettings, saveAssets, saveDarkMode,
    createDefaultSettings,
  } from './storage';
  import { t, tx } from './i18n';

  import Header from './components/Header.svelte';
  import Hero from './components/Hero.svelte';
  import GlobalSettings from './components/GlobalSettings.svelte';
  import PortfolioEditor from './components/PortfolioEditor.svelte';
  import ResultsPanel from './components/ResultsPanel.svelte';
  import HowItWorks from './components/HowItWorks.svelte';
  import AlgoSection from './components/AlgoSection.svelte';
  import OssSection from './components/OssSection.svelte';

  import { uuid } from './util';
  import { runRebalance as apiRunRebalance, runRebalanceInBrowser } from './api';
  import { parsePortfolio, buildExport } from './portfolio-io';

  export let baseCurrencies: string[];
  export let rebalanceEngine: RebalanceEngine;

  const defaultSettings = createDefaultSettings(baseCurrencies[0]);
  let settings: Settings = defaultSettings;
  let assets: Asset[] = [];
  let lastResult: RebalanceResponse | null = null;
  let resultSettings: Settings = defaultSettings;
  let error: UiError | null = null;
  let loading = false;
  let dark = false;

  let fileInput: HTMLInputElement;

  // Keep the document title in sync with the active language.
  $: document.title = $t('meta.title');

  onMount(() => {
    settings = loadSettings(baseCurrencies);
    assets = loadAssets();
    dark = loadDarkMode();
    document.documentElement.classList.toggle('dark', dark);
  });

  function updateSettings(patch: Partial<Settings>) {
    settings = { ...settings, ...patch };
    saveSettings(settings);
  }

  async function addAsset() {
    const id = uuid();
    assets = [...assets, {
      id,
      ticker: '',
      provider: null,
      currency: null,
      desiredPercentage: 0,
      shares: 0,
      fees: 0,
      percentageFee: false,
    }];
    saveAssets(assets);

    await tick();
    document.getElementById(`ticker-${id}`)?.focus();
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
      const submittedSettings = { ...settings };
      const run = rebalanceEngine === 'frontend' ? runRebalanceInBrowser : apiRunRebalance;
      const r = await run(submittedSettings, assets);
      if (r.ok) {
        error = null;
        resultSettings = submittedSettings;
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
    const result = parsePortfolio(text, baseCurrencies);
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
  <div class="container">
    <Hero />

    {#if error}
      <div class="notice error-box" role="alert">
        {#if error.kind === 'validation'}
          {error.items.map((i) => $t(i.key, i.params)).join(' · ')}
        {:else if error.kind === 'key'}
          {$t(error.key, error.params)}
        {:else}
          {error.text}
        {/if}
      </div>
    {/if}

    <GlobalSettings
      increment={settings.increment}
      baseCurrency={settings.baseCurrency}
      {baseCurrencies}
      onlyBuy={settings.onlyBuy}
      optimalRedistribute={settings.optimalRedistribute}
      fractionalShares={settings.fractionalShares}
      on:update={e => updateSettings(e.detail)}
    />
    <PortfolioEditor
      {assets}
      {loading}
      baseCurrency={settings.baseCurrency}
      on:addAsset={addAsset}
      on:removeAsset={e => removeAsset(e.detail)}
      on:updateAsset={e => updateAsset(e.detail.id, e.detail.patch)}
      on:run={runRebalance}
    />

    <ResultsPanel result={lastResult} settings={resultSettings} />
  </div>

  <HowItWorks />
  <AlgoSection />
  <OssSection />
</main>

<footer>
  <div class="container footer-inner">
    <span>{$t('footer.brand')}</span>
    <div class="footer-links">
      <a href="https://github.com/PestoENGINE/PestoENGINE" target="_blank" rel="noopener noreferrer">{$t('footer.github')}</a>
      <span>{$t('footer.license')}</span>
      <span>{$t('footer.noAnalytics')}</span>
    </div>
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
    background: var(--paper);
    border: 1px solid var(--frame);
    border-radius: var(--r);
    color: var(--ink);
    padding: 0.45rem 0.7rem;
    font-size: 0.875rem;
    font-weight: 600;
    text-decoration: none;
  }
  .skip-link:focus-visible {
    transform: translateY(0);
    opacity: 1;
    pointer-events: auto;
  }
  .skip-link:focus:not(:focus-visible) { transform: translateY(-150%); opacity: 0; }
  main:focus { outline: none; }

  .error-box { margin-bottom: 1rem; }

  footer {
    background: var(--nav);
    color: var(--on-nav-2);
    font-size: 0.8125rem;
  }
  /* Baseline alignment: the GitHub link carries extra padding for a larger
     tap target, which must not push its text below the plain labels. */
  .footer-inner {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.5rem 1.5rem;
    padding-block: 1.25rem;
  }
  .footer-links {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.5rem 1.25rem;
  }
  footer a { display: inline-block; padding-block: 0.25rem; color: var(--on-nav); text-underline-offset: 3px; }
  footer a:hover { color: var(--green); }
</style>
