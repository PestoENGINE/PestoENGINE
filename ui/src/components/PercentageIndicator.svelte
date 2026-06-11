<script lang="ts">
  import { percentagesSumTo100 } from '../util';

  export let sum: number;

  $: valid = percentagesSumTo100(sum);
  $: pct = Math.min(sum, 100);
</script>

<div class="pct-label">
  <span>Allocation total</span>
  <span class="pct-value" class:over={!valid}>{sum.toFixed(2)}%</span>
</div>
<div class="pct-bar">
  <div class="pct-fill" class:over={!valid} style="width:{pct}%"></div>
</div>

<style>
  .pct-label {
    font-size: 0.75rem;
    color: var(--text-2);
    margin-bottom: 0.375rem;
    display: flex;
    justify-content: space-between;
  }
  .pct-value { font-family: var(--mono); font-variant-numeric: tabular-nums; font-weight: 600; }
  .pct-value.over { color: var(--error); }

  .pct-bar {
    height: 3px;
    background: var(--border);
    border-radius: 2px;
    margin-bottom: 0.625rem;
    overflow: hidden;
  }
  .pct-fill {
    height: 100%;
    background: var(--teal);
    border-radius: 2px;
    transition: width 0.2s;
  }
  .pct-fill.over { background: var(--error); }
</style>
