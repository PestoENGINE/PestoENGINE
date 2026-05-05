<script lang="ts">
  export let sum: number;

  $: valid = Math.abs(sum - 100) <= 0.01;
  $: pct = Math.min(sum, 100);
</script>

<div class="pct-label">
  <span>Allocation total</span>
  <span style="font-family:var(--mono);font-variant-numeric:tabular-nums;font-weight:600;color:{valid ? 'var(--text)' : 'var(--error)'}">
    {sum.toFixed(2)}%
  </span>
</div>
<div class="pct-bar">
  <div class="pct-fill {valid ? '' : 'over'}" style="width:{pct}%"></div>
</div>
