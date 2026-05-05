<script lang="ts">
  import type { Settings } from '../types';
  import { createEventDispatcher } from 'svelte';

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
    on:input={e => dispatch('update', { increment: parseFloat((e.target as HTMLInputElement).value) || 0 })}
    class="field mono"
  />
  <div class="field-hint">Use 0 to rebalance without adding cash.</div>
</div>

<label class="check-row" style="cursor:pointer">
  <input
    type="checkbox"
    checked={onlyBuy}
    on:change={e => dispatch('update', { onlyBuy: (e.target as HTMLInputElement).checked })}
  />
  <div>
    <div class="check-text">Only buy</div>
    <div class="check-hint">Never sell existing positions</div>
  </div>
</label>

<label class="check-row" style="cursor:pointer;margin-bottom:0">
  <input
    type="checkbox"
    checked={optimalRedistribute}
    on:change={e => dispatch('update', { optimalRedistribute: (e.target as HTMLInputElement).checked })}
  />
  <div>
    <div class="check-text">Optimal redistribute</div>
    <div class="check-hint">Knapsack DP, minimise leftover cash</div>
  </div>
</label>
