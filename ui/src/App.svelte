<script lang="ts">
  import { onMount, tick } from 'svelte';
  import type { Asset, Settings, RebalanceResponse } from './types';
  import {
    loadSettings, loadAssets, loadDarkMode,
    saveSettings, saveAssets, saveDarkMode,
    DEFAULT_SETTINGS,
  } from './storage';

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
  let error: string | null = null;
  let loading = false;
  let dark = false;

  let fileInput: HTMLInputElement;

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
    error = null;
    lastResult = null;
    try {
      const r = await apiRunRebalance(settings, assets);
      if (r.ok) {
        resultSettings = { ...settings };
        lastResult = r.data;
        await tick();
        document.getElementById('results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else {
        error = r.error;
      }
    } catch {
      error = 'Request failed. Is the backend running?';
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

    const note = result.sumWarning
      ? ' (Note: percentages do not sum to 100. Fix before running.)'
      : '';
    if (!confirm(`This will replace your current portfolio.${note} Continue?`)) return;

    settings = result.settings;
    assets = result.assets;
    lastResult = null;
    error = null;
    saveSettings(settings);
    saveAssets(assets);
  }
</script>

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

<Hero />

<div class="tool-section">
  {#if error}
    <div class="error-box" role="alert">{error}</div>
  {/if}

  <div class="tool-grid">

    <!-- Settings panel -->
    <div class="panel">
      <div class="panel-head">
        <span class="panel-title">Settings</span>
      </div>
      <div class="panel-body">
        <GlobalSettings
          increment={settings.increment}
          onlyBuy={settings.onlyBuy}
          optimalRedistribute={settings.optimalRedistribute}
          on:update={e => updateSettings(e.detail)}
        />
      </div>
    </div>

    <!-- Assets panel -->
    <div class="panel">
      <div class="panel-head">
        <span class="panel-title">Assets</span>
        <button type="button" class="add-btn" on:click={addAsset}>+ Add asset</button>
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

    <!-- Result panel (owns its own panel shell) -->
    <ResultsPanel result={lastResult} settings={resultSettings} />

  </div>
</div>

<TrustRail />
<HowItWorks />
<AlgoSection />
<OssSection />

<footer>
  <span>PestoENGINE – Portfolio Rebalancing</span>
  <div class="footer-links">
    <a href="https://github.com/PestoENGINE/PestoENGINE" target="_blank" rel="noopener noreferrer">GitHub</a>
    <span class="footer-sep">·</span>
    <span>MIT License</span>
    <span class="footer-sep">·</span>
    <span>No analytics</span>
  </div>
</footer>

<style>
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
  @media (max-width: 600px) {
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
    color: rgba(240,237,232,0.3);
    text-decoration: none;
  }
  footer a:hover { color: var(--teal); }
  .footer-sep { color: rgba(240,237,232,0.1); }
</style>
