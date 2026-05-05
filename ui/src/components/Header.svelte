<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let exportDisabled = false;
  export let dark = false;

  const dispatch = createEventDispatcher<{
    requestImport: void;
    requestExport: void;
    toggleDark: void;
  }>();
</script>

<nav>
  <img src="/brand-logo-nav.svg" alt="PestoENGINE" class="wordmark-logo" />
  <div class="nav-actions">
    <button type="button" class="nav-btn" on:click={() => dispatch('requestImport')}>Import</button>
    <div class="nav-sep"></div>
    <button
      type="button"
      class="nav-btn"
      on:click={() => dispatch('requestExport')}
      disabled={exportDisabled}
    >Export</button>
    <div class="nav-sep"></div>
    <button
      type="button"
      class="nav-btn icon-btn"
      on:click={() => dispatch('toggleDark')}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {#if dark}
        <!-- Sun icon -->
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
        <!-- Moon icon -->
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
  }
  .nav-actions {
    display: flex;
    gap: 1rem;
    align-items: center;
  }
  @media (max-width: 500px) {
    nav {
      height: auto;
      flex-direction: column;
      align-items: flex-start;
      padding-top: 0.625rem;
      padding-bottom: 0.625rem;
      gap: 0.375rem;
    }
    .nav-actions { padding-left: 5px; }
  }
  .nav-btn {
    font-family: var(--sans);
    font-size: 0.8125rem;
    color: rgba(255,255,255,0.5);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.25rem 0;
  }
  .nav-btn:hover:not(:disabled) { color: rgba(255,255,255,0.9); }
  .nav-btn:disabled { opacity: 0.3; cursor: not-allowed; }
  .icon-btn { display: flex; align-items: center; padding: 0.25rem; }
  .nav-sep {
    width: 1px;
    height: 16px;
    background: rgba(255,255,255,0.12);
  }
</style>
