<div style="border-top:1px solid var(--border)">
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
            <div class="how-step-text">Enter the cash you want to deploy this period. Enable buy-only mode (default) to ensure PestoENGINE never triggers a sale. Enable knapsack mode to maximise cash deployment. Set cash to 0 to rebalance without adding new capital.</div>
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
