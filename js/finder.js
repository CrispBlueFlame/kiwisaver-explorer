// "Find my fund" — transparent scoring over the current snapshot.
const Finder = {};

const WEIGHT_LABEL = ["Ignore", "A little", "Somewhat", "A lot"];
const TYPE_ORDER = { Defensive: 0, Conservative: 1, Balanced: 2, Growth: 3, Aggressive: 4 };
const HORIZON_TYPE = [
  { max: 3, order: 1 },   // few years -> Conservative
  { max: 9, order: 2 },   // 5-10yr    -> Balanced
  { max: 20, order: 3 },  // 10+       -> Growth
  { max: 999, order: 4 }, // decades   -> Aggressive
];

function pct(values, v) {
  // percentile (0..1) of v within values; higher value -> higher pct
  if (v == null || !values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  let below = 0;
  for (const x of sorted) if (x < v) below++;
  return below / (sorted.length - 1 || 1);
}

Finder.read = function (form) {
  const fd = new FormData(form);
  return {
    risk: fd.get("risk") || "",
    horizon: fd.get("horizon") ? +fd.get("horizon") : null,
    balance: +fd.get("balance") || 10000,
    feeW: +fd.get("fee_weight"),
    returnW: +fd.get("return_weight"),
    ethical: fd.get("ethical") === "on",
    historyOnly: fd.get("history_only") === "on",
  };
};

Finder.targetOrder = function (p) {
  if (p.risk) return TYPE_ORDER[p.risk];
  if (p.horizon != null) {
    for (const b of HORIZON_TYPE) if (p.horizon <= b.max) return b.order;
  }
  return null;
};

Finder.rank = function (p) {
  let pool = KS.funds.filter((f) => f.type); // need a type to reason about
  if (p.ethical) pool = pool.filter((f) => f.ethical);
  if (p.historyOnly) pool = pool.filter((f) => f.has_history);

  const fees = pool.map((f) => f.fee).filter((v) => v != null);
  const rets = pool.map((f) => f.return_5yr ?? f.return_1yr).filter((v) => v != null);
  const target = Finder.targetOrder(p);

  const scored = pool.map((f) => {
    let score = 0;
    const reasons = [];

    // suitability (dominant)
    if (target != null) {
      const d = Math.abs(f.type_order - target);
      const add = d === 0 ? 45 : d === 1 ? 25 : d === 2 ? 8 : 0;
      score += add;
      if (d === 0) reasons.push({ t: "Matches your risk level", k: "" });
      else if (d === 1) reasons.push({ t: "Close to your risk level", k: "neutral" });
      else reasons.push({ t: `${f.type} — differs from your profile`, k: "warn" });
    } else {
      reasons.push({ t: f.type, k: "neutral" });
    }

    // fee
    const feePctl = pct(fees, f.fee); // higher = more expensive
    if (feePctl != null && p.feeW > 0) {
      score += p.feeW * (1 - feePctl) * 12;
      if (feePctl <= 0.25) reasons.push({ t: `Low fee (${KS.fmtPct(f.fee)})`, k: "" });
      else if (feePctl >= 0.8) reasons.push({ t: `High fee (${KS.fmtPct(f.fee)})`, k: "warn" });
    }

    // returns
    const r = f.return_5yr ?? f.return_1yr;
    const rLabel = f.return_5yr != null ? "5yr" : "1yr";
    const retPctl = pct(rets, r);
    if (retPctl != null && p.returnW > 0) {
      score += p.returnW * retPctl * 12;
      if (retPctl >= 0.75) reasons.push({ t: `Strong ${rLabel} return (${KS.fmtPct(r)})`, k: "" });
    }
    if (f.return_5yr == null) reasons.push({ t: "No 5yr track record", k: "warn" });

    if (f.ethical) reasons.push({ t: "Ethical / responsible", k: "" });
    if (f.has_history) reasons.push({ t: "Long data history", k: "neutral" });

    return { f, score, reasons, feeCost: KS.feeCost(f.fee, p.balance) };
  });

  scored.sort((a, b) => b.score - a.score);
  return scored;
};

Finder.ladder = function (type) {
  const step = KS.riskInfo(type).step;
  let s = "";
  for (let i = 1; i <= 5; i++) s += `<i class="rung ${i <= step ? "on" : ""}"></i>`;
  return s;
};

Finder.render = function () {
  const form = document.getElementById("finder-form");
  const p = Finder.read(form);
  const ranked = Finder.rank(p).slice(0, 10);
  const list = document.getElementById("finder-results");
  const count = document.getElementById("match-count");
  const costNote = document.getElementById("finder-cost");

  count.textContent = ranked.length ? `Top ${ranked.length} of ${KS.funds.length} funds` : "No matches";

  if (ranked.length) {
    const cheapest = ranked.reduce((a, b) => ((b.feeCost ?? 9e9) < (a.feeCost ?? 9e9) ? b : a));
    costNote.innerHTML =
      `At a $${p.balance.toLocaleString("en-NZ")} balance, estimated annual fees range roughly ` +
      `<b>${KS.fmtMoney(Math.min(...ranked.map((x) => x.feeCost ?? Infinity)))}</b>–` +
      `<b>${KS.fmtMoney(Math.max(...ranked.map((x) => x.feeCost ?? 0)))}</b> across these matches.`;
  } else {
    costNote.textContent = "";
  }

  list.innerHTML = ranked
    .map(
      (x, i) => `
    <li class="fund-card" style="border-left:4px solid ${KS.typeColor(x.f.type)}">
      <span class="rank">${i + 1}</span>
      <span class="fname">${x.f.name}</span>
      <span class="fprov">${x.f.provider} · ${x.f.type}
        <span class="risk-ladder" title="${KS.riskInfo(x.f.type).blurb}">${Finder.ladder(x.f.type)}</span></span>
      <span class="stats">
        <span class="stat"><b class="${KS.signClass(x.f.return_5yr ?? x.f.return_1yr)}">${KS.fmtPct(x.f.return_5yr ?? x.f.return_1yr)}</b><span>${x.f.return_5yr != null ? "5yr ret" : "1yr ret"}</span></span>
        <span class="stat"><b>${KS.fmtPct(x.f.fee)}</b><span>fee</span></span>
        <span class="stat"><b>${KS.fmtMoney(x.feeCost)}</b><span>fee/yr</span></span>
      </span>
      <ul class="reasons">${x.reasons.map((r) => `<li class="tag ${r.k}">${r.t}</li>`).join("")}
        <li>${Compare.button(x.f.id)}</li></ul>
    </li>`
    )
    .join("");
};

Finder.init = function () {
  const form = document.getElementById("finder-form");
  form.addEventListener("input", (e) => {
    if (e.target.name === "fee_weight")
      document.getElementById("fee_weight_out").textContent = WEIGHT_LABEL[+e.target.value];
    if (e.target.name === "return_weight")
      document.getElementById("return_weight_out").textContent = WEIGHT_LABEL[+e.target.value];
    Finder.render();
  });
  Finder.render();
};
