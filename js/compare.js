// Side-by-side fund comparison. A small shared "tray" of selected funds.
const Compare = { ids: [], chart: null, MAX: 4 };
const CMP_COLORS = ["#35c4a0", "#4aa3ff", "#e0a34a", "#e0685a"];

Compare.has = (id) => Compare.ids.includes(id);

Compare.toggle = function (id) {
  if (Compare.has(id)) Compare.ids = Compare.ids.filter((x) => x !== id);
  else if (Compare.ids.length < Compare.MAX) Compare.ids.push(id);
  Compare.sync();
};

Compare.clear = function () {
  Compare.ids = [];
  Compare.sync();
};

Compare.sync = function () {
  const badge = document.getElementById("compare-badge");
  badge.textContent = Compare.ids.length;
  badge.hidden = Compare.ids.length === 0;
  // reflect state on any visible compare buttons
  document.querySelectorAll("[data-cmp]").forEach((b) => {
    const on = Compare.has(+b.dataset.cmp);
    b.classList.toggle("on", on);
    b.textContent = on ? "✓ Comparing" : "＋ Compare";
  });
  if (!document.getElementById("view-compare").hidden) Compare.render();
};

const METRICS = [
  { label: "Provider", get: (f) => f.provider },
  { label: "Type", get: (f) => f.type || "—" },
  { label: "Risk", get: (f) => (f.type ? `${KS.riskInfo(f.type).step}/5 (${f.risk_band}/7)` : "—") },
  { label: "Annual fee", get: (f) => KS.fmtPct(f.fee), best: (f) => -(f.fee ?? Infinity) },
  { label: "Fee/yr on $50k", get: (f) => KS.fmtMoney(KS.feeCost(f.fee, 50000)), best: (f) => -(f.fee ?? Infinity) },
  { label: "1yr return", get: (f) => KS.fmtPct(f.return_1yr), best: (f) => f.return_1yr ?? -Infinity, sign: true, raw: (f) => f.return_1yr },
  { label: "5yr return", get: (f) => KS.fmtPct(f.return_5yr), best: (f) => f.return_5yr ?? -Infinity, sign: true, raw: (f) => f.return_5yr },
  { label: "History 2015–2022", get: (f) => (f.has_history ? "Yes" : "—") },
];

Compare.render = function () {
  const funds = Compare.ids.map((id) => KS.funds.find((f) => f.id === id)).filter(Boolean);
  const empty = document.getElementById("cmp-empty");
  const wrap = document.getElementById("cmp-table-wrap");
  const chartPanel = document.getElementById("cmp-chart-panel");

  if (!funds.length) {
    empty.hidden = false;
    wrap.hidden = true;
    chartPanel.hidden = true;
    return;
  }
  empty.hidden = true;
  wrap.hidden = false;
  chartPanel.hidden = false;

  const head =
    `<tr><th></th>` +
    funds.map((f, i) => `<th style="color:${CMP_COLORS[i]}">${f.name}<button class="cmp-x" data-cmp="${f.id}" title="Remove">×</button></th>`).join("") +
    `</tr>`;
  const rows = METRICS.map((m) => {
    // find best value in row for subtle highlighting
    let bestIdx = -1;
    if (m.best) {
      let bv = -Infinity;
      funds.forEach((f, i) => {
        const v = m.best(f);
        if (v > bv) { bv = v; bestIdx = i; }
      });
    }
    return (
      `<tr><td class="cmp-label">${m.label}</td>` +
      funds
        .map((f, i) => {
          const cls = [m.sign ? KS.signClass(m.raw(f)) : "", i === bestIdx ? "cmp-best" : ""].join(" ");
          return `<td class="${cls}">${m.get(f)}</td>`;
        })
        .join("") +
      `</tr>`
    );
  }).join("");

  document.getElementById("cmp-body").innerHTML = head + rows;
  Compare.draw(funds);
};

Compare.draw = function (funds) {
  const years = 20, amount = 100, freq = 12;
  const labels = ["now"];
  for (let y = 1; y <= years; y++) labels.push("yr " + y);
  const datasets = funds.map((f, i) => {
    const rate = KS.assumedReturn(f) ?? 4;
    const r = rate / 100;
    const pr = Math.pow(1 + r, 1 / freq) - 1;
    let bal = 0;
    const data = [0];
    for (let y = 1; y <= years; y++) {
      for (let p = 0; p < freq; p++) bal = (bal + amount) * (1 + pr);
      data.push(Math.round(bal));
    }
    return { label: `${f.name} (${rate.toFixed(1)}%)`, data, borderColor: CMP_COLORS[i], backgroundColor: CMP_COLORS[i] + "22", tension: 0.25, pointRadius: 0 };
  });
  if (Compare.chart) Compare.chart.destroy();
  Compare.chart = new Chart(document.getElementById("cmp-canvas"), {
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

Compare.init = function () {
  const sel = document.getElementById("cmp-add");
  [...KS.funds]
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach((f) => sel.add(new Option(`${f.name} — ${f.provider}`, f.id)));
  sel.addEventListener("change", () => {
    if (sel.value) Compare.toggle(+sel.value);
    sel.value = "";
  });
  document.getElementById("cmp-clear").addEventListener("click", () => Compare.clear());
  Compare.render();
};

// small reusable compare button for cards/detail
Compare.button = (id) =>
  `<button class="cmp-btn ${Compare.has(id) ? "on" : ""}" data-cmp="${id}" type="button">${Compare.has(id) ? "✓ Comparing" : "＋ Compare"}</button>`;
