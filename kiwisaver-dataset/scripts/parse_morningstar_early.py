#!/usr/bin/env python3
"""Extract category-level 1-year average returns from the 2010-2013 Morningstar
KiwiSaver Performance Survey PDFs (Wayback-recovered) into a labelled early-returns
layer: data/morningstar-early/category-returns.csv (quarter, category, return_1yr, assets_m).

We deliberately keep only the "Peer Group Averages" category rows, not individual
funds: Morningstar names funds by manager+category (ANZ/ING/OnePath, Tower/Fisher,
AXA/AON have since merged), so a per-fund join to the 2026 snapshot would be a
silent-drift trap. Category averages map cleanly onto the fund `type` we assign.

Two PDF layouts appear across the four years:
  A (2010-06 .. 2011-09): an explicit "1-year" column; we read the value at that
     header's character offset (its position drifts between issues).
  B (2011-12 .. 2013-09): a "Total Returns % p.a" block whose first number is the
     1-year return; we take the first figure after the assets value.

Run with plain python3 (needs pdftotext on PATH).  --debug prints raw vs parsed.
"""
import os, re, csv, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
RAW = os.path.join(DATASET, "data/morningstar-surveys/raw")
OUTDIR = os.path.join(DATASET, "data/morningstar-early")
OUT = os.path.join(OUTDIR, "category-returns.csv")

CATS = ["Conservative", "Moderate", "Balanced", "Growth", "Aggressive"]
DEBUG = "--debug" in sys.argv


def quarter_end(stem):
    """local filename '2010-06' -> quarter end date '2010-06-30'."""
    y, m = stem.split("-")
    last = {"03": "31", "06": "30", "09": "30", "12": "31"}[m]
    return f"{y}-{m}-{last}"


def pdf_lines(path):
    out = subprocess.run(["pdftotext", "-layout", path, "-"],
                         capture_output=True, text=True, check=True).stdout
    return out.splitlines()


def floats_with_pos(line):
    """[(value, start_col, end_col)] for every number (incl. negative/decimal) in the line."""
    res = []
    for m in re.finditer(r"-?\d+(?:\.\d+)?", line):
        res.append((float(m.group()), m.start(), m.end()))
    return res


def find_header_offset(lines, i, label_variants):
    """Search a few lines above the peer-group block for a header containing one of
    the label variants; return the character offset (start) of that label."""
    for j in range(i, max(i - 6, 0) - 1, -1):
        for lab in label_variants:
            k = lines[j].find(lab)
            if k != -1:
                return k
    return None


def parse_layout_a(lines, i, one_year_off):
    """Category 'Average' or 'Peer Group' rows: read the number spanning the 1-year offset."""
    rows = {}
    for line in lines[i:i + 40]:
        m = re.match(r"\s*(Conservative(?:\s*\(Including Default Options\))?|Moderate|Balanced|Growth|Aggressive)\b", line)
        if not m:
            continue
        cat = m.group(1).split(" (")[0]
        if cat in rows:
            continue
        nums = floats_with_pos(line)
        if not nums:
            continue
        # pick the number whose column span is closest to the 1-year header offset
        best = min(nums, key=lambda t: abs(t[1] - one_year_off))
        assets = nums[0][0] if nums else None
        rows[cat] = (best[0], assets)
        if DEBUG:
            print(f"    A {cat:14s} 1yr={best[0]:6.2f}  raw='{line.strip()[:90]}'")
    return rows


def parse_layout_b(lines, i):
    """Peer-group rows under 'Total Returns % p.a': first figure after assets = 1yr."""
    rows = {}
    for line in lines[i:i + 40]:
        m = re.search(r"\b(Conservative|Moderate|Balanced|Growth|Aggressive)\b", line)
        if not m:
            continue
        cat = m.group(1)
        if cat in rows:
            continue
        # numbers after the category label only (skips any "(Including Default Options)" text)
        tail = line[m.end():]
        nums = [v for v, _, _ in floats_with_pos(tail)]
        if len(nums) < 2:
            continue
        assets, one_yr = nums[0], nums[1]
        rows[cat] = (one_yr, assets)
        if DEBUG:
            print(f"    B {cat:14s} 1yr={one_yr:6.2f} assets={assets:8.1f}  raw='{line.strip()[:90]}'")
    return rows


def parse_file(path):
    lines = pdf_lines(path)
    i = next((k for k, l in enumerate(lines) if "Peer Group Averages" in l), None)
    if i is None:
        return {}
    header = lines[i]
    if "1-year" in header or "1 year" in header.lower():
        off = header.find("1-year")
        return parse_layout_a(lines, i, off)
    # layout A where the label sits on a header line just above/below
    off = find_header_offset(lines, i, ["1-year", "1 year"])
    if off is not None and "Total Returns" not in "\n".join(lines[max(i - 3, 0):i + 3]):
        return parse_layout_a(lines, i, off)
    return parse_layout_b(lines, i)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    files = sorted(f for f in os.listdir(RAW) if re.match(r"\d{4}-\d{2}\.pdf$", f))
    out_rows = []
    for f in files:
        stem = f[:-4]
        q = quarter_end(stem)
        if DEBUG:
            print(f"\n{f}  ({q})")
        rows = parse_file(os.path.join(RAW, f))
        for cat in CATS:
            if cat in rows:
                one_yr, assets = rows[cat]
                out_rows.append({"quarter": q, "category": cat,
                                 "return_1yr": round(one_yr, 2),
                                 "assets_m": round(assets, 1) if assets is not None else ""})
        got = ",".join(c for c in CATS if c in rows)
        print(f"{f} -> {q}: {len([c for c in CATS if c in rows])}/5 categories ({got})")

    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["quarter", "category", "return_1yr", "assets_m"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"\nwrote {OUT}: {len(out_rows)} rows across {len(files)} surveys")


if __name__ == "__main__":
    main()
