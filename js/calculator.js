// Investment calculator: forward projection + historical backtest.
const Calc = { mode: "projection", chart: null, built: false };

// ---- simulation engines ----
// Forward projection: compound contributions at a steady annual rate (returns are net of fees).
function project(amount, freq, years, annualPct, startBal) {
  const r = annualPct / 100;
  const periodRate = Math.pow(1 + r, 1 / freq) - 1;
  let bal = startBal;
  const points = [{ label: "now", bal }];
  const yearBal = [startBal];
  for (let y = 1; y <= years; y++) {
    for (let p = 0; p < freq; p++) bal = (bal + amount) * (1 + periodRate);
    yearBal.push(bal);
    points.push({ label: "yr " + y, bal });
  }
  const contrib = startBal + amount * freq * years;
  // estimate fees paid: fee% of the average balance each year (illustrative; already inside the net return)
  return { points, final: bal, contrib, growth: bal - contrib, yearBal };
}

// Historical backtest: replay a fund's real annual returns from startYear to the last year we have.
function backtest(fund, amount, freq, startYear, startBal) {
  const yr = KS.yearlyReturns(fund.hkey);
  const years = Object.keys(yr).map(Number).filter((y) => y >= startYear).sort();
  let bal = startBal;
  const points = [{ label: String(startYear - 1), bal }];
  const monthly = (amount * freq) / 12;
  for (const y of years) {
    const mRate = Math.pow(1 + yr[y] / 100, 1 / 12) - 1;
    for (let m = 0; m < 12; m++) bal = (bal + monthly) * (1 + mRate);
    points.push({ label: String(y), bal });
  }
  const contrib = startBal + monthly * 12 * years.length;
  return { points, final: bal, contrib, growth: bal - contrib, years };
}

Calc.selectedFund = function () {
  return KS.funds.find((f) => f.id === Calc.fundId);
};

Calc.setMode = function (mode) {
  const f = Calc.selectedFund();
  if (mode === "backtest" && !f.has_history) return; // guard
  Calc.mode = mode;
  document.getElementById("calc-mode-proj").classList.toggle("active", mode === "projection");
  document.getElementById("calc-mode-back").classList.toggle("active", mode === "backtest");
  document.getElementById("calc-proj-only").hidden = mode === "backtest";
  document.getElementById("calc-back-only").hidden = mode === "projection";
  Calc.render();
};

Calc.onFundChange = function () {
  const f = Calc.selectedFund();
  // default the assumed rate to the fund's own recent average
  const assumed = KS.assumedReturn(f);
  const rateEl = document.getElementById("calc-rate");
  rateEl.value = assumed != null ? assumed.toFixed(1) : "5.0";
  document.getElementById("calc-rate-hint").textContent =
    assumed != null
      ? `Starts from this fund's recent average (${assumed.toFixed(1)}% a year). Change it to test other scenarios.`
      : "No return history for this fund — using a default. Adjust to suit.";
  // backtest availability
  const backBtn = document.getElementById("calc-mode-back");
  backBtn.disabled = !f.has_history;
  backBtn.title = f.has_history ? "" : "No 2015–2022 history for this fund";
  if (!f.has_history && Calc.mode === "backtest") Calc.setMode("projection");
  // populate start years
  const sy = document.getElementById("calc-startyear");
  const yrs = Object.keys(KS.yearlyReturns(f.hkey)).sort();
  sy.innerHTML = yrs.map((y) => `<option value="${y}">${y}</option>`).join("");
  Calc.render();
};

Calc.render = function () {
  if (!window.Chart) return;
  const f = Calc.selectedFund();
  const amount = +document.getElementById("calc-amount").value || 0;
  const freq = +document.getElementById("calc-freq").value;
  const startBal = +document.getElementById("calc-start").value || 0;
  const freqWord = { 52: "week", 26: "fortnight", 12: "month" }[freq];
  const res = document.getElementById("calc-results");
  let sim, headline, sentence, extra, benchSeries = null, benchFinal = null, band = null;

  if (Calc.mode === "projection") {
    const years = +document.getElementById("calc-years").value;
    const rate = +document.getElementById("calc-rate").value || 0;
    sim = project(amount, freq, years, rate, startBal);
    const feeEst = estFees(sim.yearBal, f.fee);
    headline = `Could grow to about <b>${KS.fmtMoney(sim.final)}</b>`;
    sentence =
      `Putting in <b>$${amount}</b> a ${freqWord} for <b>${years} years</b> at an assumed ` +
      `<b>${rate}%</b> a year, you'd contribute about <b>${KS.fmtMoney(sim.contrib)}</b> of your own money ` +
      `and gain roughly <b>${KS.fmtMoney(sim.growth)}</b> in growth.`;
    extra = feeEst != null
      ? `Estimated fees over that time: about <b>${KS.fmtMoney(feeEst)}</b> (already reflected in the returns above).`
      : "";
    // best/worst band from the fund's own historical volatility (±1 standard deviation of annual returns)
    const vol = f.has_history ? KS.returnVolatility(f.hkey) : null;
    if (vol != null) {
      const lo = project(amount, freq, years, rate - vol, startBal);
      const hi = project(amount, freq, years, rate + vol, startBal);
      band = { lo: lo.points.map((p) => p.bal), hi: hi.points.map((p) => p.bal), vol, loFinal: lo.final, hiFinal: hi.final };
      extra += `${extra ? " " : ""}Good and bad runs happen: based on this fund's past year-to-year swings (about ` +
        `±${vol.toFixed(1)}%), the outcome could plausibly land between <b>${KS.fmtMoney(lo.final)}</b> and ` +
        `<b>${KS.fmtMoney(hi.final)}</b>.`;
    }
    // benchmark: average fund of the same type
    const bench = KS.benchmarkReturn(f.type);
    if (bench != null) {
      const b = project(amount, freq, years, bench, startBal);
      benchSeries = b.points.map((p) => p.bal);
      benchFinal = b.final;
    }
  } else {
    const startYear = +document.getElementById("calc-startyear").value;
    sim = backtest(f, amount, freq, startYear, startBal);
    const endYear = sim.years[sim.years.length - 1];
    headline = `Would have been worth about <b>${KS.fmtMoney(sim.final)}</b> by end ${endYear}`;
    sentence =
      `Putting in <b>$${amount}</b> a ${freqWord} from <b>${startYear}</b> to <b>${endYear}</b> ` +
      `using this fund's real returns, you'd have contributed about <b>${KS.fmtMoney(sim.contrib)}</b> ` +
      `and ended with <b>${KS.fmtMoney(sim.growth)}</b> of growth on top.`;
    extra = "Based on the fund's reported annual returns; contributions are spread evenly across each year.";
  }

  const ri = KS.riskInfo(f.type);
  res.innerHTML = `
    <div class="results-head"><h2>${f.name}</h2></div>
    <p class="muted">${f.provider} · ${f.type || "—"} · fee ${KS.fmtPct(f.fee)}</p>
    ${f.type ? `<p class="risk-blurb"><span class="risk-ladder">${riskLadder(ri.step)}</span> ${ri.blurb}</p>` : ""}
    <p class="calc-headline">${headline}</p>
    <p class="calc-sentence">${sentence}</p>
    ${benchFinal != null ? `<p class="muted">For comparison, the average ${f.type} fund would reach about <b>${KS.fmtMoney(benchFinal)}</b>.</p>` : ""}
    ${extra ? `<p class="disclaimer">${extra}</p>` : ""}`;

  Calc.draw(sim, benchSeries, f, band);
};

function estFees(yearBal, feePct) {
  if (feePct == null) return null;
  let fees = 0;
  for (let i = 1; i < yearBal.length; i++) fees += (feePct / 100) * ((yearBal[i - 1] + yearBal[i]) / 2);
  return Math.round(fees);
}

function riskLadder(step) {
  let s = "";
  for (let i = 1; i <= 5; i++) s += `<i class="rung ${i <= step ? "on" : ""}"></i>`;
  return s;
}

Calc.draw = function (sim, benchSeries, f, band) {
  const labels = sim.points.map((p) => p.label);
  const balance = sim.points.map((p) => p.bal);
  // cumulative contributions line
  const perStep =
    Calc.mode === "projection"
      ? (+document.getElementById("calc-amount").value || 0) * (+document.getElementById("calc-freq").value)
      : (+document.getElementById("calc-amount").value || 0) * (+document.getElementById("calc-freq").value);
  const start = +document.getElementById("calc-start").value || 0;
  const contribLine = sim.points.map((_, i) => start + perStep * i);

  const datasets = [
    { label: "Your balance", data: balance, borderColor: KS.typeColor(f.type), backgroundColor: KS.typeColor(f.type) + "33", fill: band ? false : true, tension: 0.25 },
    { label: "Money you put in", data: contribLine, borderColor: "#8fa3b5", borderDash: [5, 4], pointRadius: 0, tension: 0 },
  ];
  if (band) {
    // shaded ±1 std-dev band: draw the low line, then fill up to the high line
    const c = KS.typeColor(f.type);
    datasets.push({ label: "Worse run", data: band.lo, borderColor: c + "55", pointRadius: 0, tension: 0.25, fill: false });
    datasets.push({ label: "Better run", data: band.hi, borderColor: c + "55", pointRadius: 0, tension: 0.25, fill: "-1", backgroundColor: c + "22" });
  }
  if (benchSeries) datasets.push({ label: `Average ${f.type} fund`, data: benchSeries, borderColor: "#c0c8d0", borderDash: [2, 3], pointRadius: 0, tension: 0.25 });

  if (Calc.chart) Calc.chart.destroy();
  Calc.chart = new Chart(document.getElementById("calc-canvas"), {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#e6edf3" } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${KS.fmtMoney(c.parsed.y)}` } },
      },
      scales: {
        x: { ticks: { color: "#8fa3b5" }, grid: { color: "#22303f" } },
        y: { ticks: { color: "#8fa3b5", callback: (v) => KS.fmtMoney(v) }, grid: { color: "#22303f" } },
      },
    },
  });
};

Calc.init = function () {
  const input = document.getElementById("calc-fund");
  // default to a fund that has history so backtest is available
  const def = KS.funds.find((f) => f.has_history && f.type === "Balanced") || KS.funds.find((f) => f.has_history) || KS.funds[0];
  Calc.fundId = def.id;
  input.value = KS.fundLabel(def);

  input.addEventListener("change", () => {
    const f = KS.fundFromLabel(input.value);
    if (f) { Calc.fundId = f.id; Calc.onFundChange(); }
    else input.value = KS.fundLabel(Calc.selectedFund()); // restore last valid pick
  });
  document.getElementById("calc-mode-proj").addEventListener("click", () => Calc.setMode("projection"));
  document.getElementById("calc-mode-back").addEventListener("click", () => Calc.setMode("backtest"));
  ["calc-amount", "calc-freq", "calc-years", "calc-rate", "calc-startyear", "calc-start"].forEach((id) =>
    document.getElementById(id).addEventListener("input", () => Calc.render())
  );
  Calc.onFundChange();
  Calc.built = true;
};
