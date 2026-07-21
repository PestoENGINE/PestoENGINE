<script lang="ts">
  import { createEventDispatcher, onDestroy } from 'svelte';
  import type { TickerResult } from '../types';
  import { searchTickers } from '../api';
  import { t } from '../i18n';

  export let value: string = '';
  export let id: string = '';
  export let cellStyle: boolean = false;
  export let invalid: boolean = false;

  const dispatch = createEventDispatcher<{
    change: {
      ticker: string;
      provider: string | null;
      currency: string | null;
    };
  }>();

  let results: TickerResult[] = [];
  let open = false;
  let activeIndex = -1;
  let rateLimited = false;
  let searchError = false;
  let debounceTimer: ReturnType<typeof setTimeout>;
  let searchSeq = 0;

  // Namespace internal element ids so multiple instances do not collide.
  $: listboxId = id ? `${id}-listbox` : 'autocomplete-listbox';
  $: optionId = (i: number) => `${listboxId}-opt-${i}`;

  function onInput(e: Event) {
    const q = (e.target as HTMLInputElement).value.trim().toUpperCase();
    value = q;
    dispatch('change', { ticker: q, provider: null, currency: null });

    clearTimeout(debounceTimer);
    // Bumped before the early return so an in-flight response for the old
    // query cannot reopen the dropdown after the field was cleared.
    const seq = ++searchSeq;
    results = [];
    rateLimited = false;
    searchError = false;
    open = false;

    if (q.length < 2) return;

    debounceTimer = setTimeout(() => fetchResults(q, seq), 300);
  }

  async function fetchResults(q: string, seq: number) {
    try {
      const outcome = await searchTickers(q);
      if (seq !== searchSeq) return; // stale: a newer keystroke happened since
      if (outcome.ok) {
        results = outcome.results;
        rateLimited = false;
        searchError = false;
        activeIndex = -1;
        open = true;
      } else if (outcome.rateLimited) {
        rateLimited = true;
        open = true;
      } else {
        searchError = true;
        open = true;
      }
    } catch {
      // Network error: keep the field manually editable, but show a lightweight hint.
      if (seq !== searchSeq) return;
      searchError = true;
      open = true;
    }
  }

  function select(result: TickerResult) {
    value = result.ticker;
    dispatch('change', {
      ticker: result.ticker,
      provider: result.provider,
      currency: result.currency,
    });
    open = false;
    results = [];
    activeIndex = -1;
  }

  function onBlur() {
    setTimeout(() => { open = false; activeIndex = -1; }, 150);
  }

  function onKeydown(e: KeyboardEvent) {
    if (!open || results.length === 0) {
      if (e.key === 'Escape') { open = false; activeIndex = -1; }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIndex = Math.min(activeIndex + 1, results.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIndex = Math.max(activeIndex - 1, -1);
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault();
      select(results[activeIndex]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      open = false;
      activeIndex = -1;
    }
  }

  onDestroy(() => clearTimeout(debounceTimer));
</script>

<div class="autocomplete-wrapper">
  <input
    {id}
    type="text"
    {value}
    placeholder="VWCE.DE"
    on:input={onInput}
    on:blur={onBlur}
    on:keydown={onKeydown}
    class={`${cellStyle ? 'cell-input ticker' : 'field mono'} ticker-input`}
    autocomplete="off"
    spellcheck="false"
    role="combobox"
    aria-label={$t('autocomplete.aria')}
    aria-expanded={open}
    aria-controls={listboxId}
    aria-autocomplete="list"
    aria-activedescendant={activeIndex >= 0 ? optionId(activeIndex) : undefined}
    aria-invalid={invalid ? 'true' : undefined}
  />
  {#if open}
    <ul id={listboxId} class="autocomplete-dropdown" role="listbox">
      {#if rateLimited}
        <li role="presentation" class="autocomplete-empty">{$t('autocomplete.rateLimited')}</li>
      {:else if searchError}
        <li role="presentation" class="autocomplete-empty">{$t('autocomplete.error')}</li>
      {:else}
        {#each results as result, i (`${result.ticker}:${result.exchange}`)}
          <li
            id={optionId(i)}
            role="option"
            aria-selected={activeIndex === i}
            on:mousedown|preventDefault={() => select(result)}
            class="autocomplete-item"
            class:active={activeIndex === i}
          >
            <span class="autocomplete-ticker">{result.ticker}</span>
            <span class="autocomplete-name">
              {result.name}
              {#if result.exchange}{' · '}{result.exchange}{/if}
              {#if result.currency}{' · '}{result.currency}{/if}
            </span>
          </li>
        {/each}
        {#if results.length === 0}
          <li role="presentation" class="autocomplete-empty">{$t('autocomplete.noResults')}</li>
        {/if}
      {/if}
    </ul>
  {/if}
</div>

<style>
  .autocomplete-wrapper {
    position: relative;
    width: 100%;
  }

  .autocomplete-dropdown {
    position: absolute;
    top: calc(100% + 2px);
    left: 0;
    z-index: 10;
    padding: 2px 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    max-height: 220px;
    width: max-content;
    min-width: 100%;
    max-width: 420px;
    overflow-y: auto;
    scrollbar-width: none;
  }

  .autocomplete-dropdown::-webkit-scrollbar {
    display: none;
  }

  .autocomplete-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 4px 10px;
    cursor: pointer;
  }

  .autocomplete-item:hover,
  .autocomplete-item.active {
    background: var(--bg);
  }

  .autocomplete-ticker {
    font-family: var(--mono);
    font-size: 0.75rem;
    color: var(--text);
  }

  .autocomplete-name {
    font-size: 0.6875rem;
    font-style: italic;
    color: var(--text-2);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .autocomplete-item + .autocomplete-item {
    border-top: 1px solid var(--border);
  }

  .autocomplete-empty {
    padding: 6px 10px;
    font-size: 0.8125rem;
    color: var(--text-3);
  }
</style>
