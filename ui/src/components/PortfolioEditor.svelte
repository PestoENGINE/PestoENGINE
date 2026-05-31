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
