<div class="hero">
  <div class="hero-bg-text" aria-hidden="true">VAGF<br>VWCE<br>SWDA</div>
  <div class="hero-inner">
    <div class="hero-kicker">Rebalancing execution engine</div>
    <h1 class="hero-headline">You know your allocation.<br>Now know exactly what to buy.</h1>
    <p class="hero-sub">Enter your ETF allocations, current holdings, and monthly cash. PestoENGINE returns the exact number of shares to buy, with your broker's fee structure already priced in.</p>
  </div>
</div>

<style>
  .hero {
    background: var(--hero-bg);
    padding: clamp(2rem, 4vw, 2.75rem) clamp(1rem, 4vw, 2rem);
    border-bottom: 1px solid var(--hero-border);
    position: relative;
    overflow: hidden;
  }
  .hero-bg-text {
    position: absolute;
    right: -0.5rem;
    top: 50%;
    transform: translateY(-50%);
    font-family: var(--mono);
    font-size: clamp(4rem, 10vw, 8rem);
    font-weight: 600;
    color: rgba(255,255,255,0.03);
    letter-spacing: -0.02em;
    pointer-events: none;
    user-select: none;
    line-height: 1.1;
  }
  :global(html.dark) .hero-bg-text { color: rgba(26,156,163,0.08); }
  .hero-inner { max-width: 700px; position: relative; }
  .hero-kicker {
    font-family: var(--mono);
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--teal);
    margin-bottom: 1rem;
  }
  .hero-headline {
    font-size: clamp(1.5rem, 4vw, 2rem);
    font-weight: 500;
    line-height: 1.2;
    color: var(--hero-text);
    margin-bottom: 1rem;
    letter-spacing: -0.02em;
  }
  .hero-sub {
    font-size: clamp(0.9375rem, 2vw, 1.0625rem);
    color: var(--hero-sub);
    line-height: 1.6;
    max-width: 560px;
    margin: 0;
  }
</style>
