<script lang="ts">
  import type { Settings } from '../types';
  import { createEventDispatcher } from 'svelte';
  import { inputNumber, inputChecked } from '../util';
  import { t } from '../i18n';

  export let increment: number;
  export let onlyBuy: boolean;
  export let optimalRedistribute: boolean;
  export let fractionalShares: boolean;

  const dispatch = createEventDispatcher<{ update: Partial<Settings> }>();
</script>

<div class="field-group">
  <label class="field-label" for="increment">{$t('settings.cashToDeploy')}</label>
  <input
    id="increment"
    type="number"
    min="0"
    step="any"
    value={increment}
    on:change={e => dispatch('update', { increment: inputNumber(e) })}
    class="field mono"
  />
</div>

<label class="check-row">
  <input
    type="checkbox"
    checked={onlyBuy}
    on:change={e => dispatch('update', { onlyBuy: inputChecked(e) })}
  />
  <div>
    <div class="check-text">{$t('settings.onlyBuy')}</div>
    <div class="check-hint">{$t('settings.onlyBuyHint')}</div>
  </div>
</label>

<label class="check-row">
  <input
    type="checkbox"
    checked={fractionalShares}
    on:change={e => dispatch('update', { fractionalShares: inputChecked(e) })}
  />
  <div>
    <div class="check-text">{$t('settings.fractional')}</div>
    <div class="check-hint">{$t('settings.fractionalHint')}</div>
  </div>
</label>

<label class="check-row flush" class:disabled={fractionalShares}>
  <input
    type="checkbox"
    checked={optimalRedistribute}
    disabled={fractionalShares}
    on:change={e => dispatch('update', { optimalRedistribute: inputChecked(e) })}
  />
  <div>
    <div class="check-text">{$t('settings.optimal')}</div>
    <div class="check-hint">
      {fractionalShares ? $t('settings.optimalHintDisabled') : $t('settings.optimalHint')}
    </div>
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

  .check-row {
    display: flex;
    gap: 0.625rem;
    align-items: flex-start;
    margin-bottom: 0.875rem;
    cursor: pointer;
  }
  .check-row.flush { margin-bottom: 0; }
  .check-row.disabled { opacity: 0.5; cursor: default; }
  .check-row.disabled input[type='checkbox'] { cursor: default; }
  .check-text { font-size: 0.9375rem; font-weight: 500; }
  .check-hint { font-size: 0.75rem; color: var(--text-3); margin-top: 0.1rem; }
</style>
