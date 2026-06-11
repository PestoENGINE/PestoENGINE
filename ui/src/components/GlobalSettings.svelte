<script lang="ts">
  import type { Settings } from '../types';
  import { createEventDispatcher } from 'svelte';
  import { inputNumber, inputChecked } from '../util';

  export let increment: number;
  export let onlyBuy: boolean;
  export let optimalRedistribute: boolean;

  const dispatch = createEventDispatcher<{ update: Partial<Settings> }>();
</script>

<div class="field-group">
  <label class="field-label" for="increment">Cash to deploy</label>
  <input
    id="increment"
    type="number"
    min="0"
    step="any"
    value={increment}
    on:change={e => dispatch('update', { increment: inputNumber(e) })}
    class="field mono"
  />
  <div class="field-hint">Use 0 with Only buy off to rebalance without adding cash.</div>
</div>

<label class="check-row">
  <input
    type="checkbox"
    checked={onlyBuy}
    on:change={e => dispatch('update', { onlyBuy: inputChecked(e) })}
  />
  <div>
    <div class="check-text">Only buy</div>
    <div class="check-hint">Never sell existing positions</div>
  </div>
</label>

<label class="check-row flush">
  <input
    type="checkbox"
    checked={optimalRedistribute}
    on:change={e => dispatch('update', { optimalRedistribute: inputChecked(e) })}
  />
  <div>
    <div class="check-text">Optimal redistribute</div>
    <div class="check-hint">Knapsack DP, minimise leftover cash</div>
  </div>
</label>

<style>
  .field-group { margin-bottom: 1rem; }
  .field-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-2);
    margin-bottom: 0.35rem;
    display: block;
  }
  .field-hint { font-size: 0.75rem; color: var(--text-3); margin-top: 0.25rem; }

  .check-row {
    display: flex;
    gap: 0.625rem;
    align-items: flex-start;
    margin-bottom: 0.875rem;
    cursor: pointer;
  }
  .check-row.flush { margin-bottom: 0; }
  .check-text { font-size: 0.9375rem; font-weight: 500; }
  .check-hint { font-size: 0.75rem; color: var(--text-3); margin-top: 0.1rem; }
</style>
