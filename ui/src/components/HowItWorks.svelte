<div class="section-divider">
  <div class="content-section">
    <div class="section-kicker">How it works</div>
    <h2 class="section-headline">Three inputs. One deterministic result.</h2>

    <div class="how-grid">
      <div class="how-steps">
        <div class="how-step">
          <div class="how-num">01</div>
          <div>
            <div class="how-step-title">Set your target allocation</div>
            <div class="how-step-text">Enter each ETF ticker, your target weight, current share count, and your broker's fee. PestoENGINE fetches live prices from Yahoo Finance at calculation time, cached for 5 minutes.</div>
          </div>
        </div>
        <div class="how-step">
          <div class="how-num">02</div>
          <div>
            <div class="how-step-title">Drop in your monthly cash</div>
            <div class="how-step-text">Enter the cash you want to deploy this period. Enable buy-only mode (default) to ensure PestoENGINE never triggers a sale. Enable knapsack mode to maximise cash deployment. Set cash to 0 (with buy-only disabled) to rebalance without adding new capital.</div>
          </div>
        </div>
        <div class="how-step">
          <div class="how-num">03</div>
          <div>
            <div class="how-step-title">Get the exact buy order</div>
            <div class="how-step-text">PestoENGINE returns the exact number of shares to buy per asset, with fees already priced in, allocation drift shown, and leftover change made explicit. Same inputs always produce the same output.</div>
          </div>
        </div>
      </div>

      <div>
        <div class="code-block">
          <div class="code-header">Request: POST /v1/rebalance</div>
          <div class="code-body">
            <!-- Use HTML entities for curly braces in code display -->
            <div class="code-line"><span class="code-ln">1</span><span class="code-content ci">&#123;</span></div>
            <div class="code-line"><span class="code-ln">2</span><span class="code-content">&nbsp;&nbsp;<span class="ck">"increment"</span><span class="ci">:</span> <span class="cn">1000</span><span class="ci">,</span></span></div>
            <div class="code-line"><span class="code-ln">3</span><span class="code-content">&nbsp;&nbsp;<span class="ck">"only_buy"</span><span class="ci">:</span> <span class="cv">true</span><span class="ci">,</span></span></div>
            <div class="code-line"><span class="code-ln">4</span><span class="code-content">&nbsp;&nbsp;<span class="ck">"optimal_redistribute"</span><span class="ci">:</span> <span class="cv">true</span><span class="ci">,</span></span></div>
            <div class="code-line"><span class="code-ln">5</span><span class="code-content">&nbsp;&nbsp;<span class="ck">"assets"</span><span class="ci">: [</span></span></div>
            <div class="code-line"><span class="code-ln">6</span><span class="code-content">&nbsp;&nbsp;&nbsp;&nbsp;<span class="ci">&#123;</span></span></div>
            <div class="code-line"><span class="code-ln">7</span><span class="code-content">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="ck">"ticker"</span><span class="ci">:</span> <span class="cs">"VWCE.DE"</span><span class="ci">,</span></span></div>
            <div class="code-line"><span class="code-ln">8</span><span class="code-content">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="ck">"desired_percentage"</span><span class="ci">:</span> <span class="cn">60</span><span class="ci">,</span></span></div>
            <div class="code-line"><span class="code-ln">9</span><span class="code-content">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="ck">"shares"</span><span class="ci">:</span> <span class="cn">10</span><span class="ci">,</span></span></div>
            <div class="code-line"><span class="code-ln">10</span><span class="code-content">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="ck">"fees"</span><span class="ci">:</span> <span class="cn">3.95</span></span></div>
            <div class="code-line"><span class="code-ln">11</span><span class="code-content">&nbsp;&nbsp;&nbsp;&nbsp;<span class="ci">&#125;</span></span></div>
            <div class="code-line"><span class="code-ln">12</span><span class="code-content">&nbsp;&nbsp;<span class="ci">]</span></span></div>
            <div class="code-line"><span class="code-ln">13</span><span class="code-content ci">&#125;</span></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .how-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: clamp(2rem, 5vw, 3.5rem);
    align-items: start;
  }
  @media (max-width: 720px) { .how-grid { grid-template-columns: 1fr; } }
  .how-steps { display: flex; flex-direction: column; gap: 2rem; }
  .how-step { display: flex; gap: 1.125rem; }
  .how-num {
    font-family: var(--mono);
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--teal);
    width: 20px;
    flex-shrink: 0;
    padding-top: 0.15rem;
  }
  .how-step-title { font-weight: 600; font-size: 1rem; margin-bottom: 0.375rem; }
  .how-step-text { font-size: 0.9375rem; color: var(--text-2); line-height: 1.6; }

  .code-block {
    background: #0c1e1e;
    border-radius: var(--r);
    font-family: var(--mono);
    font-size: 0.8125rem;
    line-height: 1.8;
    overflow-x: auto;
    border: 1px solid rgba(255,255,255,0.06);
  }
  .code-header {
    padding: 0.5rem 1rem;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    font-size: 0.6875rem;
    color: rgba(240,237,232,0.3);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .code-body { padding: 1rem 1.25rem; }
  .code-line { display: flex; gap: 0; min-height: 1.4em; }
  .code-ln { width: 2ch; color: rgba(240,237,232,0.15); flex-shrink: 0; margin-right: 1.5rem; text-align: right; user-select: none; }
  .code-content { color: rgba(240,237,232,0.8); }
  .ck { color: #7dd3d6; }
  .cv { color: #f4c97e; }
  .cs { color: #a8d8a8; }
  .cn { color: #c3a6ff; }
  .ci { color: rgba(240,237,232,0.4); }
</style>
