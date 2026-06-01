<div class="trust-rail">
  <div class="trust-token">
    <svg class="trust-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
    Open source, MIT licensed
  </div>
  <div class="trust-token">
    <svg class="trust-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
    No accounts, no data stored
  </div>
  <div class="trust-token">
    <svg class="trust-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
    Self-hostable
  </div>
  <div class="trust-token">
    <svg class="trust-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
    Algorithm is documented
  </div>
</div>

<style>
  .trust-rail {
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    padding: 1rem clamp(1rem, 4vw, 2rem);
    display: flex;
    justify-content: center;
    gap: 2rem;
    flex-wrap: wrap;
    transition: background 0.2s;
  }
  .trust-token {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.875rem;
    color: var(--text-2);
  }
  .trust-icon { color: var(--teal); flex-shrink: 0; }
</style>
