// Chart builder — scatter / bar / historical line / distribution.
const Charts = { chart: null, built: false };

const NUM_FIELDS = [
  { key: "fee", label: "Fee %" },
  { key: "return_1yr", label: "1yr return %" },
  { key: "return_5yr", label: "5yr return %" },
];
const GROUP_FIELDS = [
  { key: "type", label: "Fund type" },
  { key: "provider", label: "Provider" },
  { key: "ethical", label: "Ethical (yes/no)" },
];

function fill(sel, opts) {
  sel.innerHTML = opts.map((o) => `<option value="${o.key}">${o.label}</option>`).join("");
}
function groupVal(f, key) {
  if (key === "ethical") return f.ethical ? "Ethical" : "Standard";
  return f[key] || "—";
}
function median(a) {
  if (!a.length) return null;
  const s = [...a].sort((x, y) => x - y);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

Charts.setup = function () {
  fill(document.getElementById("ch-y"), NUM_FIELDS);
  document.getElementById("ch-y").value = "return_5yr";
  fill(document.getElementById("ch-group"), GROUP_FIELDS);
  ["ch-type", "ch-x", "ch-y", "ch-group", "ch-ethical"].forEach((id) =>
    document.getElementById(id).addEventListener("input", () => Charts.render())
  );
  Charts.syncX();
  Charts.built = true;
};

Charts.syncX = function () {
  const type = document.getElementById("ch-type").value;
  const xSel = document.getElementById("ch-x");
  const xWrap = xSel.closest("label");
  if (type === "line") {
    xWrap.style.display = "none";
  } else if (type === "scatter") {
    xWrap.style.display = "";
    fill(xSel, NUM_FIELDS);
    xSel.value = "fee";
  } else {
    xWrap.style.display = "";
    fill(xSel, GROUP_FIELDS);
  }
};

Charts.pool = function () {
  const eth = document.getElementById("ch-ethical").checked;
  return KS.funds.filter((f) => f.type && (!eth || f.ethical));
};

Charts.render = function () {
  if (!window.Chart) return;
  const type = document.getElementById("ch-type").value;
  Charts.syncX();
  const yKey = document.getElementById("ch-y").value;
  const gKey = document.getElementById("ch-group").value;
  const xKey = document.getElementById("ch-x").value;
  const hint = document.getElementById("ch-hint");
  const pool = Charts.pool();
  if (Charts.chart) Charts.chart.destroy();
  const ctx = document.getElementById("ch-canvas");
  const yLabel = NUM_FIELDS.find((f) => f.key === yKey).label;

  let config;
  if (type === "scatter") {
    const groups = [...new Set(pool.map((f) => groupVal(f, gKey)))];
    config = {
      type: "scatter",
      data: {
        datasets: groups.map((g) => ({
          label: g,
          data: pool
            .filter((f) => groupVal(f, gKey) === g && f[xKey] != null && f[yKey] != null)
            .map((f) => ({ x: f[xKey], y: f[yKey], name: f.name })),
          backgroundColor: gKey === "type" ? KS.typeColor(g) : undefined,
        })),
      },
      options: scatterOpts(NUM_FIELDS.find((f) => f.key === xKey).label, yLabel),
    };
    hint.textContent = `${pool.length} funds. Each point is a fund; colour = ${gKey}.`;
  } else if (type === "bar") {
    const { labels, means, colors } = groupAgg(pool, xKey, yKey, "mean");
    config = {
      type: "bar",
      data: { labels, datasets: [{ label: `Mean ${yLabel}`, data: means, backgroundColor: colors }] },
      options: baseOpts(yLabel),
    };
    hint.textContent = `Mean ${yLabel} per ${xKey}.`;
  } else if (type === "box") {
    const { labels, ranges, medians, colors } = groupDist(pool, xKey, yKey);
    config = {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "min–max", data: ranges, backgroundColor: colors.map((c) => c + "55"), borderColor: colors, borderWidth: 1 },
          { type: "scatter", label: "median", data: medians.map((m, i) => ({ x: labels[i], y: m })), backgroundColor: "#fff", pointRadius: 4 },
        ],
      },
      options: baseOpts(yLabel),
    };
    hint.textContent = `Range (min–max) with median marker of ${yLabel} per ${xKey}.`;
  } else if (type === "line") {
    config = Charts.historyConfig(yKey, gKey, yLabel);
    hint.textContent = `Average ${yLabel} over time by ${gKey} (FMA 2015–2022). Uses funds with history only.`;
  }
  Charts.chart = new Chart(ctx, config);
};

function groupAgg(pool, gKey, yKey) {
  const map = new Map();
  pool.forEach((f) => {
    if (f[yKey] == null) return;
    const g = groupVal(f, gKey);
    (map.get(g) || map.set(g, []).get(g)).push(f[yKey]);
  });
  let entries = [...map.entries()].map(([g, arr]) => [g, arr.reduce((a, b) => a + b, 0) / arr.length]);
  entries.sort((a, b) => b[1] - a[1]);
  if (entries.length > 20) entries = entries.slice(0, 20);
  return {
    labels: entries.map((e) => e[0]),
    means: entries.map((e) => +e[1].toFixed(2)),
    colors: entries.map((e) => (gKey === "type" ? KS.typeColor(e[0]) : "#4aa3ff")),
  };
}

function groupDist(pool, gKey, yKey) {
  const map = new Map();
  pool.forEach((f) => {
    if (f[yKey] == null) return;
    const g = groupVal(f, gKey);
    (map.get(g) || map.set(g, []).get(g)).push(f[yKey]);
  });
  let entries = [...map.entries()];
  entries.sort((a, b) => median(b[1]) - median(a[1]));
  if (entries.length > 15) entries = entries.slice(0, 15);
  return {
    labels: entries.map((e) => e[0]),
    ranges: entries.map((e) => [Math.min(...e[1]), Math.max(...e[1])]),
    medians: entries.map((e) => +median(e[1]).toFixed(2)),
    colors: entries.map((e) => (gKey === "type" ? KS.typeColor(e[0]) : "#4aa3ff")),
  };
}

Charts.historyConfig = function (yKey, gKey, yLabel) {
  const hKey = yKey === "return_5yr" ? "return_5yr" : yKey === "fee" ? "fee" : "return_1yr";
  const byId = new Map(KS.funds.map((f) => [f.hkey, f]));
  // gather per group: quarter -> [values]
  const groups = new Map();
  const quarters = new Set();
  Object.entries(KS.history).forEach(([hk, series]) => {
    const f = byId.get(hk);
    if (!f) return;
    const g = groupVal(f, gKey);
    if (gKey === "provider") return; // too many lines; handled below
    series.forEach((rec) => {
      const v = rec[hKey];
      if (v == null) return;
      quarters.add(rec.quarter);
      if (!groups.has(g)) groups.set(g, new Map());
      const qm = groups.get(g);
      (qm.get(rec.quarter) || qm.set(rec.quarter, []).get(rec.quarter)).push(v);
    });
  });
  const labels = [...quarters].sort();
  const datasets = [...groups.entries()].map(([g, qm]) => ({
    label: g,
    data: labels.map((q) => {
      const arr = qm.get(q);
      return arr ? +(arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(2) : null;
    }),
    borderColor: gKey === "type" ? KS.typeColor(g) : undefined,
    spanGaps: true,
    tension: 0.25,
  }));
  return {
    type: "line",
    data: { labels, datasets },
    options: baseOpts(yLabel),
  };
};

function baseOpts(yLabel) {
  return {
    responsive: true,
    plugins: { legend: { labels: { color: "#e6edf3" } } },
    scales: {
      x: { ticks: { color: "#8fa3b5" }, grid: { color: "#22303f" } },
      y: { title: { display: true, text: yLabel, color: "#8fa3b5" }, ticks: { color: "#8fa3b5" }, grid: { color: "#22303f" } },
    },
  };
}
function scatterOpts(xLabel, yLabel) {
  const o = baseOpts(yLabel);
  o.scales.x.title = { display: true, text: xLabel, color: "#8fa3b5" };
  o.plugins.tooltip = {
    callbacks: { label: (c) => `${c.raw.name}: (${c.parsed.x}, ${c.parsed.y})` },
  };
  return o;
}
