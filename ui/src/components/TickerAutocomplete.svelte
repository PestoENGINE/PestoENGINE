<!-- ui/src/components/TickerAutocomplete.svelte -->
<script lang="ts">
  import { createEventDispatcher, onDestroy } from 'svelte';

  export let value: string = '';
  export let id: string = '';
  export let cellStyle: boolean = false;

  interface TickerResult {
    ticker: string;
    name: string;
    exchange: string;
    type: string;
  }

  const dispatch = createEventDispatcher<{ change: string }>();

  let results: TickerResult[] = [];
  let open = false;
  let activeIndex = -1;
  let debounceTimer: ReturnType<typeof setTimeout>;

  function onInput(e: Event) {
    const q = (e.target as HTMLInputElement).value.trim().toUpperCase();
    value = q;
    dispatch('change', q);

    clearTimeout(debounceTimer);
    results = [];
    open = false;

    if (q.length < 2) return;

    debounceTimer = setTimeout(() => fetchResults(q), 300);
  }

  async function fetchResults(q: string) {
    try {
      const res = await fetch(`/v1/tickers/search?q=${encodeURIComponent(q)}`);
      if (!res.ok) return;
      const data = await res.json();
      results = data.results ?? [];
      activeIndex = -1;
      open = true;
    } catch {
      // network error - field remains manually editable
    }
  }

  function select(ticker: string) {
    value = ticker;
    dispatch('change', ticker);
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
      select(results[activeIndex].ticker);
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
    class={cellStyle ? 'cell-input ticker' : 'field mono'}
    style="text-transform: uppercase;"
    autocomplete="off"
    spellcheck="false"
    role="combobox"
    aria-label="Ticker symbol"
    aria-expanded={open}
    aria-controls="autocomplete-listbox"
    aria-autocomplete="list"
    aria-activedescendant={activeIndex >= 0 ? `autocomplete-opt-${activeIndex}` : undefined}
  />
  {#if open}
    <ul id="autocomplete-listbox" class="autocomplete-dropdown" role="listbox">
      {#each results as result, i (`${result.ticker}:${result.exchange}`)}
        <li
          id="autocomplete-opt-{i}"
          role="option"
          aria-selected={activeIndex === i}
          on:mousedown|preventDefault={() => select(result.ticker)}
          class="autocomplete-item"
          class:active={activeIndex === i}
        >
          <span class="autocomplete-ticker">{result.ticker}</span>
          <span class="autocomplete-name">{result.name}</span>
        </li>
      {/each}
      {#if results.length === 0}
        <li role="presentation" class="autocomplete-empty">No results</li>
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
    list-style: none;
    margin: 0;
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
    font-family: var(--ff-mono);
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
