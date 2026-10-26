<script lang="ts">
  import type { Settings } from '../types';
  import { createEventDispatcher } from 'svelte';
  import { inputNumber, inputChecked } from '../util';
  import { t } from '../i18n';

  export let increment: number;
  export let baseCurrency: string;
  export let baseCurrencies: string[];
  export let onlyBuy: boolean;
  export let optimalRedistribute: boolean;
  export let fractionalShares: boolean;

  const dispatch = createEventDispatcher<{ update: Partial<Settings> }>();
</script>

<div class="settings" role="group" aria-label={$t('panel.settings')}>
  <div class="cash">
    <label class="cash-label" for="increment">{$t('settings.cashToDeploy')}</label>
    <div class="cash-field">
      <input
        id="increment"
        type="number"
        min="0"
        step="any"
        value={increment}
        on:change={e => dispatch('update', { increment: inputNumber(e) })}
        class="field mono cash-input"
      />
      <select
        value={baseCurrency}
        on:change={e => dispatch('update', {
          baseCurrency: (e.target as HTMLSelectElement).value,
        })}
        class="field mono currency-select"
        aria-label={$t('settings.baseCurrency')}
      >
        {#each baseCurrencies as currency}
          <option value={currency}>{currency}</option>
        {/each}
      </select>
    </div>
  </div>

  <div class="options">
    <label class="option">
      <input
        type="checkbox"
        class="check"
        checked={onlyBuy}
        on:change={e => dispatch('update', { onlyBuy: inputChecked(e) })}
      />
      <span class="option-label">{$t('settings.onlyBuy')}</span>
      <span class="option-hint">{$t('settings.onlyBuyHint')}</span>
    </label>

    <label class="option">
      <input
        type="checkbox"
        class="check"
        checked={fractionalShares}
        on:change={e => dispatch('update', { fractionalShares: inputChecked(e) })}
      />
      <span class="option-label">{$t('settings.fractional')}</span>
      <span class="option-hint">{$t('settings.fractionalHint')}</span>
    </label>

    <label class="option" class:disabled={fractionalShares}>
      <input
        type="checkbox"
        class="check"
        checked={optimalRedistribute}
        disabled={fractionalShares}
        on:change={e => dispatch('update', { optimalRedistribute: inputChecked(e) })}
      />
      <span class="option-label">{$t('settings.optimal')}</span>
      <span class="option-hint">
        {fractionalShares ? $t('settings.optimalHintDisabled') : $t('settings.optimalHint')}
      </span>
    </label>
  </div>
</div>

<style>
  /* Toolbar on top of the holdings sheet: shares its frame (no bottom edge)
     and its horizontal inset, so the cash label starts on the same line as
     the "Ticker" column below. */
  .settings {
    display: grid;
    grid-template-columns: 13rem minmax(0, 1fr);
    align-items: first baseline;
    gap: 1rem 2.5rem;
    padding: 0.875rem var(--cell-x) 1rem;
    border: 1px solid var(--frame);
    border-bottom: 0;
    background: var(--paper-2);
  }
  .cash-label {
    display: block;
    margin-bottom: 0.375rem;
    font-size: 0.9375rem;
    font-weight: 500;
    line-height: 1.4;
  }
  .cash-field { display: flex; }
  .cash-input {
    flex: 1;
    min-width: 0;
    border-radius: var(--r) 0 0 var(--r);
    font-size: 1rem;
    font-weight: 500;
    text-align: right;
  }
  .cash-input:focus,
  .currency-select:focus { position: relative; z-index: 1; }
  .currency-select {
    width: 5rem;
    margin-left: -1px;
    padding: 0 0.5rem;
    border-radius: 0 var(--r) var(--r) 0;
    font-size: 0.875rem;
    color: var(--ink-2);
    appearance: auto;
    cursor: pointer;
  }

  /* One row per option, columns shared through subgrid: box, name, hint. */
  .options {
    display: grid;
    grid-template-columns: 1rem auto minmax(0, 1fr);
    column-gap: 0.625rem;
    row-gap: 0.5rem;
  }
  .option {
    display: grid;
    grid-column: 1 / -1;
    grid-template-columns: subgrid;
    align-items: baseline;
    cursor: pointer;
  }
  .option.disabled { opacity: 0.5; cursor: default; }
  .option-label { font-size: 0.9375rem; font-weight: 500; line-height: 1.4; }
  .option-hint { font-size: 0.8125rem; line-height: 1.4; color: var(--ink-3); }

  .check {
    appearance: none;
    -webkit-appearance: none;
    display: grid;
    place-content: center;
    align-self: center;
    width: 1rem;
    height: 1rem;
    margin: 0;
    border: 1px solid var(--rule-strong);
    border-radius: 2px;
    background: var(--paper);
    cursor: pointer;
  }
  .check:hover:not(:disabled) { border-color: var(--frame); }
  .check:checked { border-color: var(--frame); background: var(--green); }
  .check:checked::after {
    content: '';
    width: 0.3rem;
    height: 0.55rem;
    border: solid var(--on-green);
    border-width: 0 2px 2px 0;
    transform: translateY(-1px) rotate(45deg);
  }
  .check:disabled { cursor: default; }

  @media (max-width: 860px) {
    .settings { grid-template-columns: minmax(0, 1fr); }
    .cash { max-width: 18rem; }
  }
  /* Phones: the hint moves under the option name. */
  @media (max-width: 600px) {
    .cash { max-width: none; }
    .currency-select { font-size: 16px; }
    .options { grid-template-columns: 1rem minmax(0, 1fr); row-gap: 0.625rem; }
    .option-hint { grid-column: 2; }
  }
</style>
