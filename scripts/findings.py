#!/usr/bin/env python3
"""Reproduce every headline finding in FINDINGS.md straight from the published data.

Reads data/current-funds.json and data/fma-history.json (the same files the site
loads) and prints each figure with its sample size, so anyone can check the claims
without reading the site's JavaScript.

Run: python3 scripts/findings.py
No dependencies beyond the Python standard library.
"""
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

GROWTH_ASSETS = ["aus_equities", "intl_equities", "listed_property", "unlisted_property"]
TYPES = ["Defensive", "Conservative", "Balanced", "Growth", "Aggressive"]


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def pearson(xs, ys):
    mx, my = st.mean(xs), st.mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    return cov / (sx * sy) if sx and sy else float("nan")


def spearman(a, b):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    return pearson(ranks(a), ranks(b))


def hdr(n, title):
    print(f"\n{'=' * 70}\nFINDING {n}: {title}\n{'=' * 70}")


def latest_alloc(records):
    for rec in reversed(records):
        if rec.get("alloc"):
            return rec["alloc"]
    return None


def mean_1yr(records, lo, hi):
    vals = [r["return_1yr"] for r in records
            if r["return_1yr"] is not None and lo <= r["quarter"][:4] <= hi]
    return st.mean(vals) if len(vals) >= 2 else None


def finding_fees(funds):
    hdr(1, "Fees vary about 8x, and index funds cost roughly 3x less than the median")
    fees = [f["fee"] for f in funds if f["fee"] is not None]
    med = st.median(fees)
    print(f"n = {len(fees)} funds with a stated annual fee")
    print(f"  fee range        : {min(fees):.2f}% to {max(fees):.2f}%  (about {max(fees)/max(min(fees),0.25):.0f}x spread)")
    print(f"  median fee       : {med:.2f}%")
    print(f"  mean fee         : {st.mean(fees):.2f}%")
    simp = sorted({f["fee"] for f in funds if "SIMPLICITY" in (f["provider"] or "").upper()})
    if simp:
        print(f"  Simplicity (index): {', '.join(f'{v:.2f}%' for v in simp)}  "
              f"=> {med/simp[0]:.1f}x cheaper than the median fund")
    for t in TYPES:
        tf = [f["fee"] for f in funds if f["type"] == t and f["fee"] is not None]
        if tf:
            print(f"    {t:<13} n={len(tf):>3}  median fee {st.median(tf):.2f}%")


def finding_fee_vs_return(funds):
    hdr(2, "Paying more does not buy more: fee and net return are uncorrelated")
    pairs = [(f["fee"], f["return_5yr"]) for f in funds
             if f["fee"] is not None and f["return_5yr"] is not None]
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    print(f"n = {len(pairs)} funds with both a fee and a 5-year net return")
    print(f"  Pearson r(fee, 5yr net return) = {pearson(xs, ys):+.3f}   (0 = no relationship)")
    print("  within risk category (controls for the fact that riskier funds earn more):")
    for t in ["Conservative", "Balanced", "Growth", "Aggressive"]:
        tp = [(f["fee"], f["return_5yr"]) for f in funds
              if f["type"] == t and f["fee"] is not None and f["return_5yr"] is not None]
        if len(tp) > 5:
            r = pearson([p[0] for p in tp], [p[1] for p in tp])
            print(f"    {t:<13} n={len(tp):>3}  r(fee, 5yr net) = {r:+.3f}")
    print("  Reading: overall no link; in the higher-risk categories the link is")
    print("  negative, i.e. the pricier funds tended to deliver slightly less, not more.")


def finding_persistence(funds, hist):
    hdr(3, "Past performance is a weak, inconsistent guide (honest persistence check)")
    byid = {f["id"]: f for f in funds}
    early, late = {}, {}
    for f in funds:
        recs = hist.get(f["hkey"])
        if not recs:
            continue
        e = mean_1yr(recs, "2016", "2018")
        l = mean_1yr(recs, "2020", "2022")
        if e is not None and l is not None:
            early[f["id"]], late[f["id"]] = e, l
    ids = [i for i in early if i in late]
    a = [early[i] for i in ids]
    b = [late[i] for i in ids]
    print(f"n = {len(ids)} funds with returns in both 2016-2018 and 2020-2022")
    print(f"  raw rank persistence (Spearman rho)          = {spearman(a, b):+.3f}")
    print("  BUT that is mostly the risk level repeating, not skill. Within category:")
    pe, pl = [], []
    for t in ["Conservative", "Balanced", "Growth", "Aggressive"]:
        tids = [i for i in ids if byid[i]["type"] == t]
        if len(tids) < 8:
            continue
        ta = [early[i] for i in tids]
        tb = [late[i] for i in tids]
        print(f"    {t:<13} n={len(tids):>3}  within-category rho = {spearman(ta, tb):+.3f}")
        me, ml = st.mean(ta), st.mean(tb)
        pe += [x - me for x in ta]
        pl += [x - ml for x in tb]
    print(f"  pooled, de-meaned by category rho            = {spearman(pe, pl):+.3f}")
    print("  Reading: within a category, past performance is only a modest and")
    print("  inconsistent guide (Aggressive funds barely persist at all). Combined")
    print("  with Finding 2, the picture is that neither price nor a fund's recent")
    print("  ranking is a reliable way to pick a future winner. Cost is the one")
    print("  lever you can actually see and control up front.")


def finding_allocation(funds, hist):
    hdr(4, "Same label, same portfolio: funds of one type hold near-identical asset mixes")
    rows = []
    for f in funds:
        recs = hist.get(f["hkey"])
        if not recs:
            continue
        a = latest_alloc(recs)
        if not a:
            continue
        tot = sum(v for v in a.values() if v is not None)
        if tot < 90 or tot > 110:
            continue
        g = sum((a.get(k) or 0) for k in GROWTH_ASSETS)
        rows.append((f["type"], g))
    print("growth-asset share (equities + property) by category, latest reported quarter:")
    for t in TYPES:
        g = sorted(r[1] for r in rows if r[0] == t)
        if len(g) >= 5:
            q1, q3 = g[len(g) // 4], g[3 * len(g) // 4]
            print(f"    {t:<13} n={len(g):>3}  mean {st.mean(g):>3.0f}%  "
                  f"std-dev {st.pstdev(g):>4.1f}pts  middle-half {q1:.0f}% to {q3:.0f}%")
    print("  Reading: within a category the mix barely moves (std-dev in single digits),")
    print("  so much of the fee gap buys near-identical exposure, not a different strategy.")


def finding_fee_drag():
    hdr(5, "What the fee gap costs in dollars over a saving lifetime")

    def project(start, monthly, years, gross_pct, fee_pct):
        net = (gross_pct - fee_pct) / 100
        bal = start
        for _ in range(years * 12):
            bal *= 1 + net / 12
            bal += monthly
        return bal

    gross = 5.0
    scenarios = [
        ("A $50,000 balance left for 30 years, no new contributions", 50000, 0, 30),
        ("$433/month (about $100/week) for 40 years, starting from zero", 0, 433, 40),
    ]
    print(f"Same {gross:.1f}% gross return for every fund; only the fee differs.")
    for label, start, monthly, years in scenarios:
        lo = project(start, monthly, years, gross, 0.25)
        med = project(start, monthly, years, gross, 0.85)
        gro = project(start, monthly, years, gross, 1.10)
        print(f"\n  {label}:")
        print(f"    0.25% index fund      : ${lo:,.0f}")
        print(f"    0.85% median fund     : ${med:,.0f}   "
              f"(${lo - med:,.0f} less, {100 * (lo - med) / lo:.0f}% of the pot)")
        print(f"    1.10% median Growth   : ${gro:,.0f}   "
              f"(${lo - gro:,.0f} less)")


def main():
    funds = load("current-funds.json")
    hist = load("fma-history.json")
    print(f"KiwiSaver Explorer, reproducible findings")
    print(f"Source: data/current-funds.json ({len(funds)} funds), data/fma-history.json")
    finding_fees(funds)
    finding_fee_vs_return(funds)
    finding_persistence(funds, hist)
    finding_allocation(funds, hist)
    finding_fee_drag()
    print(f"\n{'=' * 70}")
    print("All figures above are produced by this script from the published JSON.")
    print("Fees and returns are provider-reported to the FMA and not independently audited.")


if __name__ == "__main__":
    main()
