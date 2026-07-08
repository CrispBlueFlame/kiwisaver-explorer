#!/usr/bin/env python3
"""Build clean JSON payloads for the KiwiSaver Explorer static site.

Reads the raw dataset (../kiwisaver-dataset by default) and writes:
  data/current-funds.json  - current snapshot, the spine of the finder + explorer
  data/fma-history.json    - per-fund quarterly time series (fee/return/risk/alloc/fum/members)
  data/providers.json      - provider-level aggregates
  data/meta.json           - provenance, ranges, gaps, counts

Run: python3 scripts/build-data.py
"""
import csv, json, re, statistics, os
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
DATASET = os.path.normpath(os.path.join(SITE, "kiwisaver-dataset"))
OUT = os.path.join(SITE, "data")

# fund_type -> risk band (KiwiSaver standard guidance)
TYPE_META = {
    "Defensive":    {"order": 0, "risk_lo": 1, "risk_hi": 2, "horizon_lo": 0,  "horizon_hi": 3},
    "Conservative": {"order": 1, "risk_lo": 2, "risk_hi": 3, "horizon_lo": 1,  "horizon_hi": 4},
    "Balanced":     {"order": 2, "risk_lo": 3, "risk_hi": 4, "horizon_lo": 4,  "horizon_hi": 9},
    "Growth":       {"order": 3, "risk_lo": 4, "risk_hi": 5, "horizon_lo": 6,  "horizon_hi": 12},
    "Aggressive":   {"order": 4, "risk_lo": 5, "risk_hi": 7, "horizon_lo": 10, "horizon_hi": 40},
}

ETHICAL_HINTS = ("ETHIC", "SOCIALLY RESPONSIB", "SRI", "GREEN", "SUSTAIN", "CARBON", "CHRISTIAN", "KOURA")


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(s):
    if s is None:
        return None
    s = s.strip()
    if s == "":
        return None
    try:
        return round(float(s), 3)
    except ValueError:
        return None


def norm_name(s):
    return re.sub(r"\s+", " ", (s or "").strip().upper())


SPECIAL = {"KIWISAVER": "KiwiSaver"}
ACRONYMS = {"AE", "AMP", "ANZ", "ASB", "BNZ", "BT", "MAS", "MFL", "NZ", "NZAM", "OM",
            "QBE", "SBS", "SIL", "JMI", "KS", "ESG", "SRI", "PIE", "UK", "US", "ETF",
            "NZX", "ASX", "REIT", "SUV", "IHC"}
SMALL = {"a", "an", "and", "the", "of", "for", "in", "on", "to", "at", "by"}


def titlecase(s):
    s = (s or "").strip()
    if not s:
        return s
    tokens = re.split(r"(\s+)", s)
    out = []
    first = True
    for w in tokens:
        if w.isspace() or w == "":
            out.append(w)
            continue
        up = w.upper()
        if up in SPECIAL:
            out.append(SPECIAL[up])
        elif up in ACRONYMS:
            out.append(up)
        elif not first and w.lower() in SMALL:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:].lower())
        first = False
    return "".join(out)


def load_early_returns():
    """Morningstar peer-group category 1yr averages 2010-2013 (pre-FMA context layer).
    Keyed by category; the site maps a fund's type onto its category."""
    path = os.path.join(DATASET, "data/morningstar-early/category-returns.csv")
    if not os.path.exists(path):
        return {}
    out = defaultdict(list)
    for r in load(path):
        v = num(r.get("return_1yr"))
        if v is not None:
            out[r["category"]].append({"quarter": r["quarter"], "return_1yr": v})
    for cat in out:
        out[cat].sort(key=lambda x: x["quarter"])
    return dict(out)


def build():
    si = load(os.path.join(DATASET, "data/smart-investor/funds.csv"))
    fma = load(os.path.join(DATASET, "data/fma-quarterly/combined.csv"))

    # --- FMA history keyed by normalized fund name ---
    ALLOC = [
        ("cash", "alloc_cash_and_cash_equivalents"),
        ("nz_fixed", "alloc_new_zealand_fixed_interest"),
        ("intl_fixed", "alloc_international_fixed_interest"),
        ("aus_equities", "alloc_australasian_equities"),
        ("intl_equities", "alloc_international_equities"),
        ("listed_property", "alloc_listed_properties"),
        ("unlisted_property", "alloc_unlisted_properties"),
        ("other", "alloc_other"),
        ("commodities", "alloc_commodities"),
    ]
    hist = defaultdict(list)
    for r in fma:
        # key on fund name + scheme; the current snapshot's provider column is the scheme name,
        # so this joins each fund to its own series instead of merging same-named funds across providers.
        key = norm_name(r["fund_name"]) + "|" + norm_name(r["scheme_name"])
        rec = {
            "quarter": r["quarter"],
            "fee": num(r.get("fee_total")),
            "return_1yr": num(r.get("return_1yr")),
            "return_5yr": num(r.get("return_5yr_avg")),
            "risk": (int(num(r["risk_indicator"])) if num(r.get("risk_indicator")) else None),
            "fum": num(r.get("fum")),
            "members": (int(num(r["members"])) if num(r.get("members")) else None),
            "alloc": {k: num(r.get(col)) for k, col in ALLOC},
        }
        # drop all-null alloc to save space
        if not any(v is not None for v in rec["alloc"].values()):
            rec["alloc"] = None
        hist[key].append(rec)
    for k in hist:
        hist[k].sort(key=lambda x: x["quarter"])
        seen = {}
        for rec in hist[k]:
            seen[rec["quarter"]] = rec  # last wins on duplicate quarter
        hist[k] = list(seen.values())

    # --- current funds (spine) ---
    funds = []
    fid = 0
    for r in si:
        ftype = (r.get("fund_type") or "").strip() or None
        # drop implausible scrape artifacts: a low-risk fund cannot post a 20%+ 1yr return
        if ftype in ("Defensive", "Conservative") and (num(r.get("return_1yr")) or 0) > 15:
            continue
        name = titlecase(r["fund_name"])
        prov = titlecase(r["provider"])
        hkey = norm_name(r["fund_name"]) + "|" + norm_name(r["provider"])
        tm = TYPE_META.get(ftype, {})
        risk_band = (f"{tm['risk_lo']}–{tm['risk_hi']}" if tm else None)
        ethical = any(h in norm_name(r["fund_name"]) or h in norm_name(r["provider"]) for h in ETHICAL_HINTS)
        h_series = hist.get(hkey) or []
        history_since = h_series[0]["quarter"][:4] if len(h_series) > 1 else None
        fund = {
            "id": fid,
            "name": name,
            "provider": prov,
            "type": ftype,
            "type_order": tm.get("order"),
            "fee": num(r.get("fee_pct")),
            "return_1yr": num(r.get("return_1yr")),
            "return_5yr": num(r.get("return_5yr")),
            "risk_band": risk_band,
            "risk_lo": tm.get("risk_lo"),
            "risk_hi": tm.get("risk_hi"),
            "horizon_lo": tm.get("horizon_lo"),
            "horizon_hi": tm.get("horizon_hi"),
            "ethical": ethical,
            "has_history": hkey in hist and len(hist[hkey]) > 1,
            "history_since": history_since,
            "hkey": hkey,
        }
        funds.append(fund)
        fid += 1

    # --- provider aggregates ---
    prov_map = defaultdict(list)
    for f in funds:
        prov_map[f["provider"]].append(f)
    providers = []
    for pname, pf in sorted(prov_map.items()):
        fees = [f["fee"] for f in pf if f["fee"] is not None]
        r5 = [f["return_5yr"] for f in pf if f["return_5yr"] is not None]
        providers.append({
            "provider": pname,
            "funds": len(pf),
            "avg_fee": round(statistics.mean(fees), 3) if fees else None,
            "avg_return_5yr": round(statistics.mean(r5), 2) if r5 else None,
            "types": sorted({f["type"] for f in pf if f["type"]}),
            "ethical": any(f["ethical"] for f in pf),
        })

    # --- meta ---
    quarters = sorted({r["quarter"] for r in fma})
    meta = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "current_funds": len(funds),
            "providers": len(providers),
            "funds_with_history": sum(1 for f in funds if f["has_history"]),
            "fma_records": len(fma),
        },
        "history_range": {"first": quarters[0], "last": quarters[-1], "quarters": len(quarters)},
        "known_gaps": [
            "No consolidated quarterly fund data after Dec 2022 (FMA stopped publishing).",
            "Risk is shown as a band derived from each fund's standard type (Defensive–Aggressive); per-fund numeric risk indicators in the source could not be joined reliably and are omitted.",
            "5yr return missing for ~30% of current funds (younger funds).",
        ],
        "fund_types": list(TYPE_META.keys()),
        "sources": {
            "current": "Smart Investor (Sorted) + FundCompare snapshot",
            "history": "FMA Quarterly Fund Updates 2013-2022 (2013-2015 recovered from Wayback Machine archives)",
        },
        "license": "Data CC BY 4.0. Not financial advice.",
    }

    # only keep history for funds that reference it (saves space)
    used = {f["hkey"] for f in funds if f["has_history"]}
    hist_out = {k: v for k, v in hist.items() if k in used}

    early = load_early_returns()
    if early:
        eq = sorted({p["quarter"] for s in early.values() for p in s})
        meta["early_returns"] = {
            "source": "Morningstar KiwiSaver Performance Survey (Wayback-recovered)",
            "note": "Category peer-group averages, not individual funds. Shown as pre-2013 context only.",
            "range": {"first": eq[0], "last": eq[-1]},
            "categories": sorted(early.keys()),
        }

    os.makedirs(OUT, exist_ok=True)
    _write("current-funds.json", funds)
    _write("fma-history.json", hist_out)
    _write("providers.json", providers)
    _write("meta.json", meta)
    _write("early-returns.json", early)

    print(f"funds={len(funds)} providers={len(providers)} "
          f"history_funds={len(hist_out)} fma_rows={len(fma)}")
    print(f"ethical-flagged: {sum(1 for f in funds if f['ethical'])}")


def _write(name, obj):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
    print(f"wrote {name}: {os.path.getsize(path)/1024:.0f} KB")


if __name__ == "__main__":
    build()
