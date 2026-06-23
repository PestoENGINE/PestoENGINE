<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { t, locale, setLocale, LOCALES } from '../i18n';

  export let exportDisabled = false;
  export let dark = false;

  const dispatch = createEventDispatcher<{
    requestImport: void;
    requestExport: void;
    toggleDark: void;
  }>();

  let langOpen = false;

  // Close when focus leaves the dropdown (covers click-outside and tabbing away).
  function onLangFocusOut(e: FocusEvent & { currentTarget: HTMLDivElement }) {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) langOpen = false;
  }
</script>

<svelte:window on:keydown={(e) => { if (langOpen && e.key === 'Escape') langOpen = false; }} />

<nav aria-label={$t('nav.primaryAria')}>
  <img src="/brand-logo-nav.svg" alt="PestoENGINE" class="wordmark-logo" />
  <div class="nav-actions">
    <button type="button" class="nav-btn" on:click={() => dispatch('requestImport')}>{$t('nav.import')}</button>
    <div class="nav-sep"></div>
    <button
      type="button"
      class="nav-btn"
      on:click={() => dispatch('requestExport')}
      disabled={exportDisabled}
    >{$t('nav.export')}</button>
    <div class="nav-sep"></div>
    <div
      class="lang-dd"
      class:open={langOpen}
      on:focusout={onLangFocusOut}
    >
      <button
        type="button"
        class="nav-btn lang-current"
        aria-haspopup="menu"
        aria-expanded={langOpen}
        aria-label={$t('nav.languageAria')}
        on:click={() => (langOpen = !langOpen)}
      >
        {$locale.toUpperCase()}
        <svg class="lang-caret" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>
      {#if langOpen}
        <div class="lang-menu" role="menu">
          {#each LOCALES as l}
            <button
              type="button"
              role="menuitem"
              class="lang-option"
              class:active={$locale === l}
              aria-current={$locale === l ? 'true' : undefined}
              on:click={() => { setLocale(l); langOpen = false; }}
            >{l.toUpperCase()}</button>
          {/each}
        </div>
      {/if}
    </div>
    <div class="nav-sep"></div>
    <button
      type="button"
      class="nav-btn icon-btn"
      on:click={() => dispatch('toggleDark')}
      aria-label={dark ? $t('nav.toLightMode') : $t('nav.toDarkMode')}
    >
      {#if dark}
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4"/>
          <line x1="12" y1="2" x2="12" y2="4"/>
          <line x1="12" y1="20" x2="12" y2="22"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="2" y1="12" x2="4" y2="12"/>
          <line x1="20" y1="12" x2="22" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
      {:else}
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      {/if}
    </button>
  </div>
</nav>

<style>
  nav {
    position: sticky;
    top: 0;
    z-index: 100;
    background: var(--hero-bg);
    padding: 0 clamp(1rem, 4vw, 2rem);
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--hero-border);
  }
  .wordmark-logo {
    height: 48px;
    width: auto;
    display: block;
    flex: 0 0 auto;
  }
  .nav-actions {
    display: flex;
    gap: 1rem;
    align-items: center;
    flex: 0 0 auto;
  }
  @media (max-width: 560px) {
    nav {
      height: auto;
      flex-direction: column;
      align-items: flex-start;
      padding-top: 0.625rem;
      padding-bottom: 0.625rem;
      gap: 0.375rem;
    }
    :global(:root) { --nav-height: 102px; }
    .nav-actions {
      padding-left: 5px;
      gap: 0.7rem;
      flex-wrap: wrap;
    }
  }
  .nav-btn {
    font-family: var(--sans);
    font-size: 0.8125rem;
    color: rgba(255,255,255,0.68);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.25rem 0;
    flex: 0 0 auto;
  }
  .nav-btn:hover:not(:disabled) { color: rgba(255,255,255,0.95); }
  .nav-btn:disabled { opacity: 0.3; cursor: not-allowed; }
  .icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    padding: 0.25rem;
    flex-basis: 24px;
  }
  .icon-btn svg {
    width: 16px;
    height: 16px;
    max-width: none;
    flex: 0 0 auto;
  }
  .nav-sep {
    width: 1px;
    height: 16px;
    background: rgba(255,255,255,0.12);
    flex: 0 0 1px;
  }
  .lang-dd { position: relative; display: flex; align-items: center; }
  .lang-current { display: flex; align-items: center; gap: 0.2rem; }
  .lang-caret { transition: transform 0.15s; }
  .lang-dd.open .lang-caret { transform: rotate(180deg); }
  .lang-menu {
    position: absolute;
    top: calc(100% + 0.4rem);
    right: 0;
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 0.25rem;
    min-width: 3.25rem;
    z-index: 200;
    box-shadow: 0 6px 16px rgba(0,0,0,0.18);
  }
  .lang-option {
    font-family: var(--sans);
    font-size: 0.8125rem;
    text-align: left;
    color: var(--text-2);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.3rem 0.5rem;
    border-radius: 3px;
  }
  .lang-option:hover { background: var(--teal-light); color: var(--text); }
  .lang-option.active { color: var(--teal); font-weight: 600; }
</style>
