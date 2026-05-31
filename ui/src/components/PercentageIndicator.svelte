<script lang="ts">
  export let sum: number;

  $: valid = Math.abs(sum - 100) <= 0.01;
  $: pct = Math.min(sum, 100);
</script>

<div class="pct-label">
  <span>Allocation total</span>
  <span class="pct-value" class:over={!valid}>{sum.toFixed(2)}%</span>
</div>
<div class="pct-bar">
  <div class="pct-fill {valid ? '' : 'over'}" style="width:{pct}%"></div>
</div>
