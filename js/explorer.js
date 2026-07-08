// Data explorer — filterable, sortable table + fund drill-down.
const Explorer = {
  sortKey: "return_5yr",
  sortAsc: false,
  detailChart: null,
};

const COLS = [
  { key: "name", label: "Fund", type: "text" },
  { key: "provider", label: "Provider", type: "text" },
  { key: "type", label: "Type", type: "text" },
  { key: "risk_band", label: "Risk", type: "text", fmt: (v) => (v == null ? "—" : v + "/7") },
  { key: "fee", label: "Fee", type: "num", fmt: (v) => KS.fmtPct(v), sign: false },
  { key: "return_1yr", label: "1yr", type: "num", fmt: (v) => KS.fmtPct(v), sign: true },
  { key: "return_5yr", label: "5yr", type: "num", fmt: (v) => KS.fmtPct(v), sign: true },
];

Explorer.init = function () {
  // populate filters
  const typeSel = document.getElementById("ex-type");
  [...new Set(KS.funds.map((f) => f.type).filter(Boolean))]
    .sort((a, b) => (Finder ? 0 : 0) || a.localeCompare(b))
    .forEach((t) => typeSel.add(new Option(t, t)));
  const provSel = document.getElementById("ex-provider");
  KS.providers.forEach((p) => provSel.add(new Option(`${p.provider} (${p.funds})`, p.provider)));

  // header
  document.getElementById("ex-head").innerHTML = COLS.map(
    (c) => `<th data-key="${c.key}">${c.label}</th>`
  ).join("");
  document.querySelectorAll("#ex-head th").forEach((th) =>
    th.addEventListener("click", () => Explorer.setSort(th.dataset.key))
  );

  ["ex-search", "ex-type", "ex-provider", "ex-ethical", "ex-history"].forEach((id) =>
    document.getElementById(id).addEventListener("input", () => Explorer.render())
  );
  document.getElementById("ex-export").addEventListener("click", () => Explorer.exportCSV());
  Explorer.render();
};

Explorer.filtered = function () {
  const q = document.getElementById("ex-search").value.trim().toLowerCase();
  const type = document.getElementById("ex-type").value;
  const prov = document.getElementById("ex-provider").value;
  const eth = document.getElementById("ex-ethical").checked;
  const hist = document.getElementById("ex-history").checked;
  let rows = KS.funds.filter((f) => {
    if (type && f.type !== type) return false;
    if (prov && f.provider !== prov) return false;
    if (eth && !f.ethical) return false;
    if (hist && !f.has_history) return false;
    if (q && !(f.name.toLowerCase().includes(q) || f.provider.toLowerCase().includes(q))) return false;
    return true;
  });
  const k = Explorer.sortKey;
  const col = COLS.find((c) => c.key === k);
  rows.sort((a, b) => {
    let av = a[k], bv = b[k];
    if (col.type === "num") {
      av = av == null ? -Infinity : av;
      bv = bv == null ? -Infinity : bv;
      return Explorer.sortAsc ? av - bv : bv - av;
    }
    av = (av || "").toString();
    bv = (bv || "").toString();
    return Explorer.sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  return rows;
};

Explorer.setSort = function (key) {
  if (Explorer.sortKey === key) Explorer.sortAsc = !Explorer.sortAsc;
  else {
    Explorer.sortKey = key;
    Explorer.sortAsc = COLS.find((c) => c.key === key).type === "text";
  }
  Explorer.render();
};

Explorer.render = function () {
  const rows = Explorer.filtered();
  document.getElementById("ex-count").textContent = `${rows.length} funds`;
  document.querySelectorAll("#ex-head th").forEach((th) => {
    th.classList.toggle("sorted", th.dataset.key === Explorer.sortKey);
    th.classList.toggle("asc", Explorer.sortAsc);
  });
  document.getElementById("ex-body").innerHTML = rows
    .map(
      (f) => `<tr data-id="${f.id}">${COLS.map((c) => {
        const v = f[c.key];
        let cls = c.sign ? KS.signClass(v) : "";
        let cell = c.fmt ? c.fmt(v) : v ?? "—";
        if (c.key === "type")
          cell = `<span class="dot" style="background:${KS.typeColor(v)}"></span>${v || "—"}`;
        return `<td class="${cls}">${cell}</td>`;
      }).join("")}</tr>`
    )
    .join("");
  document.querySelectorAll("#ex-body tr").forEach((tr) =>
    tr.addEventListener("click", () => Explorer.showDetail(+tr.dataset.id))
  );
};

Explorer.showDetail = function (id) {
  const f = KS.funds.find((x) => x.id === id);
  const box = document.getElementById("fund-detail");
  const hist = f.has_history ? KS.history[f.hkey] : null;
  let histHead = "";
  if (hist && hist.length) {
    const yr = (q) => (q || "").slice(0, 4);
    const first = yr(hist[0].quarter);
    const last = yr(hist[hist.length - 1].quarter);
    const span = first === last ? first : `${first}–${last}`;
    const deep = first <= "2015";
    histHead = `<h3>History (FMA ${span})${deep ? ` <span class="depth-pill">deep · since ${first}</span>` : ""}</h3>`;
  }
  const early = hist && f.type ? KS.earlyForType(f.type) : null;
  const earlyNote = early
    ? `<p class="muted early-note">Dashed grey before 2013 is the Morningstar <b>${KS.EARLY_CAT[f.type]}</b> category 1yr average (2010–2013). Market context for this fund's risk level, not this fund itself.</p>`
    : "";
  box.hidden = false;
  box.innerHTML = `
    <h2><span class="dot" style="background:${KS.typeColor(f.type)}"></span>${f.name}
      <button class="close-x" aria-label="Close">×</button></h2>
    <p class="muted">${f.provider} · ${f.type || "—"}${f.risk_band ? " · risk " + f.risk_band + "/7" : ""}${f.ethical ? " · ethical" : ""}</p>
    ${f.type ? `<p class="risk-blurb"><span class="risk-ladder">${Finder.ladder(f.type)}</span> ${KS.riskInfo(f.type).blurb}</p>` : ""}
    <p>${Compare.button(f.id)}</p>
    <div class="detail-grid">
      <div class="metric"><b class="${KS.signClass(f.return_1yr)}">${KS.fmtPct(f.return_1yr)}</b><span>1yr return</span></div>
      <div class="metric"><b class="${KS.signClass(f.return_5yr)}">${KS.fmtPct(f.return_5yr)}</b><span>5yr return</span></div>
      <div class="metric"><b>${KS.fmtPct(f.fee)}</b><span>annual fee</span></div>
      <div class="metric"><b>${KS.fmtMoney(KS.feeCost(f.fee, 50000))}</b><span>fee on $50k</span></div>
    </div>
    ${hist ? `${histHead}<canvas id="detail-canvas" height="120"></canvas>
      ${earlyNote}
      <p class="muted">${latestAlloc(hist)}</p>`
      : `<p class="muted">No quarterly history available for this fund in the FMA dataset.</p>`}
  `;
  box.querySelector(".close-x").addEventListener("click", () => (box.hidden = true));
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });

  if (Explorer.detailChart) Explorer.detailChart.destroy();
  if (hist) {
    // unified time axis: Morningstar early quarters (2010–2013) ∪ this fund's history quarters
    const earlyMap = new Map((early || []).map((e) => [e.quarter, e.return_1yr]));
    const retMap = new Map(hist.filter((h) => h.return_1yr != null).map((h) => [h.quarter, h.return_1yr]));
    const feeMap = new Map(hist.filter((h) => h.fee != null).map((h) => [h.quarter, h.fee]));
    const labels = [...new Set([...earlyMap.keys(), ...hist.map((h) => h.quarter)])].sort();
    const at = (m) => labels.map((q) => (m.has(q) ? m.get(q) : null));
    const datasets = [
      { label: "1yr return %", data: at(retMap), borderColor: KS.typeColor(f.type), tension: 0.25, yAxisID: "y", spanGaps: true },
      { label: "fee %", data: at(feeMap), borderColor: "#8fa3b5", borderDash: [4, 4], tension: 0.25, yAxisID: "y1", spanGaps: true },
    ];
    if (early)
      datasets.push({
        label: `Morningstar ${KS.EARLY_CAT[f.type]} avg (pre-2013)`,
        data: at(earlyMap),
        borderColor: "#6b7a8a",
        borderDash: [2, 3],
        pointRadius: 2,
        tension: 0.25,
        yAxisID: "y",
        spanGaps: true,
      });
    Explorer.detailChart = new Chart(document.getElementById("detail-canvas"), {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        interaction: { mode: "index", intersect: false },
        scales: {
          y: { position: "left", title: { display: true, text: "return %" } },
          y1: { position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "fee %" } },
        },
        plugins: { legend: { labels: { color: "#e6edf3" } } },
      },
    });
  }
};

function latestAlloc(hist) {
  const withAlloc = [...hist].reverse().find((h) => h.alloc);
  if (!withAlloc) return "";
  const a = withAlloc.alloc;
  const parts = Object.entries(a)
    .filter(([, v]) => v != null && v > 0)
    .sort((x, y) => y[1] - x[1])
    .slice(0, 4)
    .map(([k, v]) => `${k.replace(/_/g, " ")} ${v.toFixed(0)}%`);
  return `Latest allocation (${withAlloc.quarter}): ` + parts.join(", ");
}

Explorer.exportCSV = function () {
  const rows = Explorer.filtered();
  const head = COLS.map((c) => c.key).join(",");
  const body = rows
    .map((f) => COLS.map((c) => JSON.stringify(f[c.key] ?? "")).join(","))
    .join("\n");
  const blob = new Blob([head + "\n" + body], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "kiwisaver-funds.csv";
  a.click();
  URL.revokeObjectURL(a.href);
};
