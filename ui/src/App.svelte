<script lang="ts">
  import { onMount, tick } from 'svelte';
  import type { Asset, Settings, RebalanceResponse, PortfolioExport } from './types';
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
    const id = crypto.randomUUID();
    assets = [...assets, { id, ticker: '', desiredPercentage: 0, shares: 0, fees: 0, percentageFee: false }];
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

    const body = {
      only_buy: settings.onlyBuy,
      increment: settings.increment,
      optimal_redistribute: settings.optimalRedistribute,
      assets: assets.map(a => ({
        ticker: a.ticker,
        desired_percentage: a.desiredPercentage,
        shares: a.shares,
        fees: a.fees,
        percentage_fee: a.percentageFee,
      })),
    };

    try {
      const res = await fetch('/v1/rebalance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (res.ok) {
        resultSettings = { ...settings };
        lastResult = await res.json() as RebalanceResponse;
        await tick();
        document.getElementById('results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else if (res.status === 422) {
        const data = await res.json();
        const msgs = Array.isArray(data.detail)
          ? data.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ')
          : typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        error = `Validation error: ${msgs}`;
      } else if (res.status === 502) {
        error = 'Market data unavailable. Check ticker symbols or try again.';
      } else {
        error = 'Request failed. Try again.';
      }
    } catch {
      error = 'Request failed. Is the backend running?';
    } finally {
      loading = false;
    }
  }

  function handleExport() {
    const now = new Date();
    const payload: PortfolioExport = {
      version: 1,
      exportedAt: now.toISOString(),
      settings,
      assets: assets.map(({ id: _id, ...rest }) => rest),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pesto-engine-portfolio-${now.toISOString().slice(0, 10)}.json`;
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
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      const importError = processImport(text);
      if (importError) {
        error = importError;
      }
    };
    reader.readAsText(file);
  }

  function processImport(text: string): string | null {
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      return 'File is not valid JSON.';
    }

    if (typeof data !== 'object' || data === null) return 'Invalid portfolio file.';
    const d = data as Record<string, unknown>;

    if (d.version !== 1) return 'Unsupported export version. Expected version 1.';
    if (typeof d.settings !== 'object' || d.settings === null) return 'Invalid portfolio file: missing settings.';
    if (!Array.isArray(d.assets) || d.assets.length === 0) return 'Invalid portfolio file: assets must be a non-empty array.';

    const s = d.settings as Record<string, unknown>;
    if (typeof s.increment !== 'number' || s.increment < 0) return 'Invalid portfolio file: invalid increment.';

    for (let i = 0; i < d.assets.length; i++) {
      const a = d.assets[i] as Record<string, unknown>;
      if (typeof a.ticker !== 'string' || !a.ticker) return `Invalid portfolio file: asset ${i + 1} missing ticker.`;
      if (typeof a.desiredPercentage !== 'number' || a.desiredPercentage < 0) return `Invalid portfolio file: asset ${i + 1} invalid desiredPercentage.`;
      if (typeof a.shares !== 'number' || a.shares < 0) return `Invalid portfolio file: asset ${i + 1} invalid shares.`;
      if (typeof a.fees !== 'number' || a.fees < 0) return `Invalid portfolio file: asset ${i + 1} invalid fees.`;
      if (typeof a.percentageFee !== 'boolean') return `Invalid portfolio file: asset ${i + 1} invalid percentageFee.`;
    }

    const sum = (d.assets as Array<{ desiredPercentage: number }>).reduce((s, a) => s + a.desiredPercentage, 0);
    const sumWarning = Math.abs(sum - 100) > 0.01 ? ' (Note: percentages do not sum to 100. Fix before running.)' : '';

    if (!confirm(`This will replace your current portfolio.${sumWarning} Continue?`)) return null;

    const newSettings: Settings = {
      increment: s.increment as number,
      onlyBuy: typeof s.onlyBuy === 'boolean' ? s.onlyBuy : DEFAULT_SETTINGS.onlyBuy,
      optimalRedistribute: typeof s.optimalRedistribute === 'boolean' ? s.optimalRedistribute : DEFAULT_SETTINGS.optimalRedistribute,
    };

    const newAssets: Asset[] = (d.assets as Array<Record<string, unknown>>).map(a => ({
      id: crypto.randomUUID(),
      ticker: a.ticker as string,
      desiredPercentage: a.desiredPercentage as number,
      shares: a.shares as number,
      fees: a.fees as number,
      percentageFee: a.percentageFee as boolean,
    }));

    settings = newSettings;
    assets = newAssets;
    lastResult = null;
    error = null;
    saveSettings(settings);
    saveAssets(assets);
    return null;
  }
</script>

<input
  bind:this={fileInput}
  type="file"
  accept=".json"
  style="display:none"
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
    <div class="error-box" style="margin-bottom:1rem" role="alert">{error}</div>
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
      <div class="panel-body" style="padding:0.625rem 1rem 1rem">
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
