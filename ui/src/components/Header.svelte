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
  <div class="container nav-inner">
    <img src="/brand-logo-nav.svg" alt="PestoENGINE" class="wordmark-logo" />
    <div class="nav-actions">
      <button type="button" class="nav-btn" on:click={() => dispatch('requestImport')}>
        <svg class="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        <span class="nav-label">{$t('nav.import')}</span>
      </button>
      <button
        type="button"
        class="nav-btn"
        on:click={() => dispatch('requestExport')}
        disabled={exportDisabled}
      >
        <svg class="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        <span class="nav-label">{$t('nav.export')}</span>
      </button>
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
  </div>
</nav>

<style>
  nav {
    position: sticky;
    top: 0;
    z-index: 100;
    height: var(--nav-height);
    background: var(--nav);
  }
  .nav-inner {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }
  .wordmark-logo {
    height: 38px;
    width: auto;
    min-width: 0;
    flex: 0 1 auto;
    object-fit: contain;
    object-position: left center;
    /* The wordmark SVG has a small inner left margin; pull it back so
       "PESTO" starts on the content edge like the rest of the page. */
    margin-left: -4px;
  }
  .nav-actions {
    display: flex;
    align-items: center;
    gap: 1.25rem;
    flex: 0 0 auto;
  }
  .nav-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    height: 2rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--on-nav-2);
    text-underline-offset: 4px;
  }
  .nav-btn:hover:not(:disabled) { color: var(--on-nav); text-decoration: underline; }
  .nav-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .nav-icon { display: none; }
  .icon-btn { width: 2rem; justify-content: center; }

  .lang-dd { position: relative; display: flex; align-items: center; }
  .lang-caret { transition: transform 0.15s; }
  .lang-dd.open .lang-caret { transform: rotate(180deg); }
  .lang-menu {
    position: absolute;
    top: calc(100% + 0.5rem);
    right: 0;
    z-index: 200;
    display: flex;
    flex-direction: column;
    min-width: 4rem;
    padding: 0.25rem 0;
    border: 1px solid var(--frame);
    border-radius: var(--r);
    background: var(--paper);
    box-shadow: var(--float-shadow);
  }
  .lang-option {
    padding: 0.375rem 0.75rem;
    font-size: 0.875rem;
    text-align: left;
    color: var(--ink-2);
  }
  .lang-option:hover { background: var(--paper-2); color: var(--ink); }
  .lang-option.active { color: var(--ink); font-weight: 600; }

  @media (max-width: 440px) {
    .wordmark-logo { height: 32px; }
    .nav-inner { gap: 0.5rem; }
    .nav-actions { gap: 0.125rem; }
    .nav-btn { min-width: 2.25rem; height: 2.5rem; justify-content: center; }
    .nav-icon { display: block; }
    /* Icon-only import/export on small screens; the label stays for screen readers. */
    .nav-label {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
    }
  }
</style>
