// Shared data store + helpers. Loaded before the view modules.
const KS = {
  funds: [],
  providers: [],
  history: {},
  meta: {},
  ready: false,
};

KS.load = async function () {
  const [funds, providers, history, meta] = await Promise.all([
    fetch("data/current-funds.json").then((r) => r.json()),
    fetch("data/providers.json").then((r) => r.json()),
    fetch("data/fma-history.json").then((r) => r.json()),
    fetch("data/meta.json").then((r) => r.json()),
  ]);
  KS.funds = funds;
  KS.providers = providers;
  KS.history = history;
  KS.meta = meta;
  KS.ready = true;
};

// formatting helpers
KS.fmtPct = (v, dp = 2) => (v == null ? "—" : v.toFixed(dp) + "%");
KS.fmtNum = (v) => (v == null ? "—" : v.toLocaleString("en-NZ"));
KS.fmtMoney = (v) => {
  if (v == null) return "—";
  if (v >= 1e9) return "$" + (v / 1e9).toFixed(1) + "b";
  if (v >= 1e6) return "$" + (v / 1e6).toFixed(0) + "m";
  if (v >= 1e3) return "$" + (v / 1e3).toFixed(0) + "k";
  return "$" + v.toFixed(0);
};
KS.signClass = (v) => (v == null ? "" : v >= 0 ? "pos" : "neg");

// colour palette by fund type, used across finder / explorer / charts
KS.TYPE_COLOR = {
  Defensive: "#4aa3ff",
  Conservative: "#35c4a0",
  Balanced: "#a0d468",
  Growth: "#e0a34a",
  Aggressive: "#e0685a",
};
KS.typeColor = (t) => KS.TYPE_COLOR[t] || "#8fa3b5";

// estimate annual fee dollar cost given a balance
KS.feeCost = (feePct, balance) =>
  feePct == null ? null : Math.round((feePct / 100) * balance);

// plain-language risk ladder shown instead of "risk 1-7" jargon
KS.RISK_INFO = {
  Defensive: { step: 1, blurb: "Very steady. Small ups and downs. Best for money you'll need within a few years." },
  Conservative: { step: 2, blurb: "Fairly steady with modest growth. Suits goals 1–4 years away." },
  Balanced: { step: 3, blurb: "A middle path — moderate ups and downs. Good for goals 5–10 years away." },
  Growth: { step: 4, blurb: "Bigger ups and downs for more long-term growth. Suits 6+ year goals." },
  Aggressive: { step: 5, blurb: "The bumpiest ride, aiming for the most growth over 10+ years." },
};
KS.riskInfo = (type) => KS.RISK_INFO[type] || { step: 0, blurb: "" };

// average net return for a fund type across the current snapshot (used as a benchmark)
KS._benchCache = null;
KS.benchmarkReturn = function (type) {
  if (!KS._benchCache) {
    KS._benchCache = {};
    for (const t of Object.keys(KS.RISK_INFO)) {
      const vals = KS.funds
        .filter((f) => f.type === t)
        .map((f) => f.return_5yr ?? f.return_1yr)
        .filter((v) => v != null);
      KS._benchCache[t] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
    }
  }
  return KS._benchCache[type];
};

// derive {year: annualReturnPct} from a fund's history (latest quarter per calendar year)
KS.yearlyReturns = function (hkey) {
  const series = KS.history[hkey];
  if (!series) return {};
  const out = {};
  for (const rec of series) if (rec.return_1yr != null) out[rec.quarter.slice(0, 4)] = rec.return_1yr;
  return out;
};

// a fund's best available "expected return" assumption for projections
KS.assumedReturn = (f) => f.return_5yr ?? f.return_1yr ?? KS.benchmarkReturn(f.type);
