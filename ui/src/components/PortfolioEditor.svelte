<script lang="ts">
  import type { Asset } from '../types';
  import AssetRow from './AssetRow.svelte';
  import PercentageIndicator from './PercentageIndicator.svelte';
  import { createEventDispatcher } from 'svelte';

  export let assets: Asset[];
  export let loading: boolean;

  const dispatch = createEventDispatcher<{
    removeAsset: string;
    updateAsset: { id: string; patch: Partial<Asset> };
    run: void;
  }>();

  $: percentageSum = assets.reduce((s, a) => s + (a.desiredPercentage || 0), 0);
  $: canRun = Math.abs(percentageSum - 100) <= 0.01 && !loading && assets.length > 0;
</script>

<PercentageIndicator sum={percentageSum} />

{#if assets.length === 0}
  <div class="assets-empty" role="status">
    No assets yet - click + Add asset.
  </div>
{:else}
  <table class="asset-table">
    <thead>
      <tr>
        <th>Ticker</th>
        <th>Target</th>
        <th>Shares</th>
        <th>Fee</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each assets as asset (asset.id)}
        <AssetRow
          {asset}
          on:update={e => dispatch('updateAsset', { id: asset.id, patch: e.detail })}
          on:remove={() => dispatch('removeAsset', asset.id)}
        />
      {/each}
    </tbody>
  </table>
{/if}

<button
  type="button"
  class="run-btn"
  on:click={() => dispatch('run')}
  disabled={!canRun}
>
  {loading ? 'Calculating…' : 'Calculate buy order'}
</button>

<style>
  .assets-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.875rem;
    color: var(--text-3);
  }

  .run-btn {
    width: 100%;
    background: var(--teal);
    color: #fff;
    border: none;
    border-radius: var(--r);
    padding: 0.7rem;
    font-family: var(--sans);
    font-size: 0.9375rem;
    font-weight: 600;
    cursor: pointer;
    margin-top: auto;
    transition: background 0.15s;
  }
  .run-btn:hover:not(:disabled) { background: var(--teal-hover); }
  .run-btn:disabled { opacity: 0.35; cursor: not-allowed; }
</style>
