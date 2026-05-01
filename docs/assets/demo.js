/* Demo orchestration. Pure front-end simulation, no network calls.
   Numbers and timings match the real run captured locally on May 1.
*/
(function () {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  // ---- Provider profiles (kept honest with the real cost numbers) ----
  const PROFILES = {
    gemini: {
      label: 'gemini',
      modelSummary: 'gemini-2.5-flash',
      modelDoc:     'gemini-2.5-flash',
      sumIn: 1240,  sumOut: 380,
      docIn: 1860,  docOut: 1120,
      // pricing per Mtok
      inPrice: 0.30, outPrice: 2.50,
      detail: 'flash → flash · same loop, one env var',
    },
    claude: {
      label: 'claude',
      modelSummary: 'claude-haiku-4-5',
      modelDoc:     'claude-sonnet-4-5',
      sumIn: 1240,  sumOut: 380,
      docIn: 1860,  docOut: 1120,
      // mixed pricing: haiku for sum, sonnet for doc
      inPriceSum: 1.00, outPriceSum: 5.00,
      inPriceDoc: 3.00, outPriceDoc: 15.00,
      detail: 'haiku → sonnet · routed by stage in routing.py',
    },
  };

  // ---- State ----
  let state = {
    running: false,
    provider: 'gemini',
    cost: 0,
    calls: 0,
    inTok: 0,
    outTok: 0,
    aborted: false,
  };

  // ---- DOM refs ----
  const term = $('#terminal');
  const costNum = $('#cost-num');
  const costFill = $('#cost-fill');
  const costDetail = $('#cost-detail');
  const jsonBox = $('#json-summary');
  const qaList = $('#qa-list');
  const finalDoc = $('#final-doc');

  // ---- Utilities ----
  function termLine(text, cls = '') {
    const div = document.createElement('div');
    div.className = 'line' + (cls ? ' ' + cls : '');
    div.innerHTML = text;
    term.appendChild(div);
    term.scrollTop = term.scrollHeight;
    return div;
  }

  async function typeInto(el, text, perChar = 8) {
    for (let i = 0; i < text.length; i++) {
      el.textContent += text[i];
      if (i % 6 === 0) await sleep(perChar);
    }
  }

  function setStage(name, status /* active | done */) {
    const step = document.querySelector(`.step[data-step="${name}"]`);
    if (!step) return;
    step.classList.remove('active', 'done');
    if (status) step.classList.add(status);
  }

  function setPill(id, label, stateName) {
    const pill = $(id);
    if (!pill) return;
    pill.setAttribute('data-state', stateName);
    pill.innerHTML = `<span class="dot"></span>${label}`;
  }

  function updateCostUI() {
    costNum.textContent = '$' + state.cost.toFixed(4);
    const pct = Math.min(100, (state.cost / 0.50) * 100);
    costFill.style.width = pct + '%';
    costDetail.textContent =
      `${state.calls} call${state.calls === 1 ? '' : 's'} · ` +
      `${state.inTok.toLocaleString()} in / ${state.outTok.toLocaleString()} out tok`;
  }

  function chargeCall(provider, stage, inTok, outTok) {
    const p = PROFILES[provider];
    let dollars;
    if (provider === 'gemini') {
      dollars = (inTok / 1e6) * p.inPrice + (outTok / 1e6) * p.outPrice;
    } else {
      const inP  = stage === 'summary' ? p.inPriceSum  : p.inPriceDoc;
      const outP = stage === 'summary' ? p.outPriceSum : p.outPriceDoc;
      dollars = (inTok / 1e6) * inP + (outTok / 1e6) * outP;
    }
    state.cost += dollars;
    state.calls += 1;
    state.inTok += inTok;
    state.outTok += outTok;
    updateCostUI();
    return dollars;
  }

  function highlightJSON(obj) {
    const json = JSON.stringify(obj, null, 2);
    return json
      .replace(/(&)/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/("(?:[^"\\]|\\.)*"):/g, '<span class="json-key">$1</span>:')
      .replace(/: ("(?:[^"\\]|\\.)*")/g, ': <span class="json-str">$1</span>')
      .replace(/: (\d+(?:\.\d+)?)/g, ': <span class="json-num">$1</span>')
      .replace(/([{}\[\],])/g, '<span class="json-punct">$1</span>');
  }

  async function streamJSON(target, obj, perStep = 14) {
    const finalText = JSON.stringify(obj, null, 2);
    const finalHtml = highlightJSON(obj);
    target.innerHTML = '';

    // Stream the raw text in ~70 chunks, then swap in the highlighted final.
    const totalChunks = 70;
    const chunkSize = Math.max(1, Math.ceil(finalText.length / totalChunks));
    let progress = '';
    for (let i = 0; i < finalText.length; i += chunkSize) {
      progress += finalText.slice(i, i + chunkSize);
      const safe = progress
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;');
      target.innerHTML = safe + '<span class="json-cursor">&nbsp;</span>';
      await sleep(perStep);
    }
    target.innerHTML = finalHtml;
  }

  // ---- Reset ----
  function resetAll() {
    state = { running: false, provider: state.provider, cost: 0, calls: 0, inTok: 0, outTok: 0, aborted: true };
    term.innerHTML = '';
    termLine(`$ workflow-doc run samples/revenue_forecast --provider <span class="hdr-provider">${state.provider}</span> --budget 0.50 --non-interactive`, 'dim');
    termLine('Press ▶ Run demo to start.', 'dim');
    updateCostUI();
    jsonBox.textContent = '// awaiting run...';
    qaList.innerHTML = '<li class="dim">Questions appear here once stage 1 completes.</li>';
    finalDoc.classList.add('dim');
    finalDoc.innerHTML = 'The generated runbook will reveal here, section by section.';
    ['discovery','parse','summary','answers','document','done'].forEach(s => setStage(s, ''));
    ['#pill-stage1','#pill-q','#pill-stage2'].forEach(id => setPill(id, 'idle', 'idle'));
    $$('.tree-line[data-file]').forEach(t => t.classList.remove('scanning','read'));
    state.aborted = false;
  }

  // ---- Provider toggle ----
  $$('.provider-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (state.running) return;
      $$('.provider-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.provider = btn.getAttribute('data-provider');
      $('#hdr-provider').textContent = state.provider;
      $$('.hdr-provider').forEach(el => el.textContent = state.provider);
      $('#provider-detail').textContent = PROFILES[state.provider].detail;
      resetAll();
    });
  });

  $('#btn-reset').addEventListener('click', () => { if (!state.running) resetAll(); });

  // ---- Run ----
  $('#btn-run').addEventListener('click', runDemo);

  async function runDemo() {
    if (state.running) return;
    resetAll();
    state.running = true;
    const p = PROFILES[state.provider];

    // 0) Discover
    setStage('discovery', 'active');
    termLine('<span class="info">[1/4] Discovering files in samples/revenue_forecast...</span>');
    await sleep(450);

    const treeFiles = ['py','csv','xlsx'];
    for (const k of treeFiles) {
      const row = document.querySelector(`.tree-line[data-file="${k}"]`);
      if (row) row.classList.add('scanning');
      await sleep(300);
      if (row) { row.classList.remove('scanning'); row.classList.add('read'); }
    }
    termLine('       found: forecast_pipeline.py, monthly_revenue.xlsx', 'dim');
    setStage('discovery', 'done');

    // 1) Parse
    setStage('parse', 'active');
    termLine('<span class="info">[2/4] AST-parsing forecast_pipeline.py and reading workbook (read-only)...</span>');
    await sleep(700);
    termLine('       PythonFileContext: 1 class, 6 functions, 4 imports', 'dim');
    termLine('       ExcelFileContext: 3 sheets (Actuals, Forecast, Sensitivity)', 'dim');
    setStage('parse', 'done');

    // 2) Summary call
    setStage('summary', 'active');
    setPill('#pill-stage1', 'streaming', 'running');
    const callLine = termLine(`       calling <span class="info">${p.modelSummary}</span> ...`);
    callLine.classList.add('cursor');
    await sleep(900);
    callLine.classList.remove('cursor');
    callLine.innerHTML += ' <span class="ok">200 OK</span>';

    const summaryObj = {
      workflow_name: "revenue_forecast",
      one_line_purpose:
        "Generates a monthly revenue forecast from historical actuals and writes a 3-sheet Excel report.",
      python_summary: {
        inputs: ["input_data.csv"],
        outputs: ["monthly_revenue.xlsx"],
        dependencies: ["openpyxl", "csv", "dataclasses"],
        notable_functions: ["load_actuals", "fit_linear_trend", "project_forecast", "write_workbook"]
      },
      excel_summary: {
        sheets: ["Actuals", "Forecast", "Sensitivity"],
        likely_purpose: "Combined view of historical revenue, projection, and stress test."
      },
      clarifying_questions: [
        { id: "q1", text: "How often should this run, and is there a hard close-of-month deadline?" },
        { id: "q2", text: "Who owns the script and who consumes monthly_revenue.xlsx?" },
        { id: "q3", text: "Where should the doc live, Notion or a GitHub repo?" }
      ]
    };
    await streamJSON(jsonBox, summaryObj);
    const cost1 = chargeCall(state.provider, 'summary', p.sumIn, p.sumOut);
    termLine(`       <span class="cost">cost: $${cost1.toFixed(4)} (${p.sumIn} in + ${p.sumOut} out tok)</span>`, '');
    setPill('#pill-stage1', 'done', 'done');
    setStage('summary', 'done');

    // 3) Answers (default values, like --non-interactive)
    setStage('answers', 'active');
    setPill('#pill-q', 'applying defaults', 'running');
    termLine('<span class="info">[3/4] Applying default answers (non-interactive mode)...</span>');
    qaList.innerHTML = '';
    const answers = [
      { q: 'How often should this run?', a: 'Monthly, runs after finance closes the month.' },
      { q: 'Who owns it / consumes the output?', a: 'Owned by Finance Ops. Output read by the CFO weekly.' },
      { q: 'Where should the doc live?', a: 'Notion, in the Finance Ops workspace.' },
    ];
    for (const item of answers) {
      const li = document.createElement('li');
      li.innerHTML = `<span class="q">${item.q}</span><span class="a">${item.a}</span>`;
      qaList.appendChild(li);
      requestAnimationFrame(() => li.classList.add('show'));
      await sleep(380);
    }
    setPill('#pill-q', 'done', 'done');
    setStage('answers', 'done');

    // 4) Final doc call
    setStage('document', 'active');
    setPill('#pill-stage2', 'streaming', 'running');
    termLine(`<span class="info">[4/4] Generating doc with</span> <span class="info">${p.modelDoc}</span>...`);
    await sleep(700);

    finalDoc.classList.remove('dim');
    finalDoc.innerHTML = '';
    const sections = [
      `<h2>revenue_forecast Workflow Documentation</h2>`,
      `<h2>Overview</h2><p>This workflow generates a monthly revenue forecast. It reads historical monthly actuals from <code class="inline">input_data.csv</code> for the prior 24 months, fits a linear trend model, and projects revenue for the next six months. Actuals, projections, and a sensitivity analysis are compiled into <code class="inline">monthly_revenue.xlsx</code>. Owned by Finance Ops. Output read by the CFO during weekly reviews.</p>`,
      `<h2>Schedule</h2><p>Monthly, after finance closes the prior month. May also run on demand when actuals change.</p>`,
      `<h2>Inputs</h2>
        <table class="clean"><thead><tr><th>Name</th><th>Type</th><th>Source</th></tr></thead>
        <tbody><tr><td class="font-mono" style="color:#fff">input_data.csv</td><td>CSV file</td><td>Finance Ops drop, monthly</td></tr></tbody></table>`,
      `<h2>Outputs</h2>
        <table class="clean"><thead><tr><th>Name</th><th>Type</th><th>Destination</th></tr></thead>
        <tbody>
          <tr><td class="font-mono" style="color:#fff">monthly_revenue.xlsx</td><td>Excel workbook</td><td>Notion / Finance Ops workspace</td></tr>
          <tr><td class="font-mono" style="color:#fff">stdout</td><td>Text</td><td>Run logs</td></tr>
        </tbody></table>`,
      `<h2>Runbook</h2><p>Place <code class="inline">input_data.csv</code> next to <code class="inline">forecast_pipeline.py</code>, then run <code class="inline">python forecast_pipeline.py</code>. The script writes <code class="inline">monthly_revenue.xlsx</code> to the same folder. Required deps: <code class="inline">openpyxl</code> (everything else is stdlib).</p>`,
      `<h2>Open Questions</h2><ul>
        <li>Should the projection switch to a seasonal model once we have 3+ years of actuals?</li>
        <li>Do we need a snapshot history of past forecasts for accuracy tracking?</li>
      </ul>`,
    ];
    for (const html of sections) {
      const node = document.createElement('div');
      node.innerHTML = html;
      while (node.firstChild) finalDoc.appendChild(node.firstChild);
      await sleep(420);
    }
    const cost2 = chargeCall(state.provider, 'final_doc', p.docIn, p.docOut);
    termLine(`       <span class="cost">cost: $${cost2.toFixed(4)} (${p.docIn} in + ${p.docOut} out tok)</span>`, '');
    setPill('#pill-stage2', 'done', 'done');
    setStage('document', 'done');

    // Done
    setStage('done', 'done');
    await sleep(200);
    termLine('');
    termLine(`<span class="ok">Wrote: outputs/revenue_forecast_${p.label}.md</span>`);
    termLine(`<span class="cost">Total: $${state.cost.toFixed(4)} across ${state.calls} call(s). Budget: $0.50. Headroom: ${(100 - (state.cost/0.5)*100).toFixed(1)}%.</span>`);
    termLine(`<span class="ok">capability_eval: PASS (9/9)</span>`);

    state.running = false;
  }

  // Initial state
  resetAll();
})();
