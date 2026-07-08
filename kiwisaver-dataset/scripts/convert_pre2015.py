#!/usr/bin/env python3
"""Convert the 2013-2015 FMA quarterly XLSB files (Wayback-recovered) into
combined.csv-schema rows and append them to data/fma-quarterly/combined.csv.

These early files use the SAS-era `submitted_disclosures` schema (GUID ids,
p_pastYear0pir returns, no risk indicator, no multi-year returns). We map them
onto the same columns the 2015-2022 Disclose rows use so build-data.py treats
them identically. Run with the pyxlsb venv:  .venv-xlsb/bin/python scripts/convert_pre2015.py
"""
import os, csv, glob, subprocess, tempfile, datetime
from datetime import date, timedelta
from pyxlsb import open_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
RAW = os.path.join(DATASET, "data/pre2015/raw")
COMBINED = os.path.join(DATASET, "data/fma-quarterly/combined.csv")
EXCEL_EPOCH = date(1899, 12, 30)

COLUMNS = [
    "quarter", "fund_number", "fund_name", "scheme_name", "provider", "fum",
    "members", "fund_start_date", "return_1yr", "return_5yr_avg", "fee_total",
    "risk_indicator", "return_yr1", "return_yr2", "return_yr3", "return_yr4",
    "return_yr5", "return_yr6", "return_yr7", "return_yr8", "return_yr9",
    "return_yr10", "alloc_cash_and_cash_equivalents",
    "alloc_new_zealand_fixed_interest", "alloc_international_fixed_interest",
    "alloc_australasian_equities", "alloc_international_equities",
    "alloc_listed_properties", "alloc_unlisted_properties", "alloc_other",
    "alloc_commodities", "target_cash_and_cash_equivalents",
    "target_new_zealand_fixed_interest", "target_international_fixed_interest",
    "target_australasian_equities", "target_international_equities",
    "target_listed_properties", "target_unlisted_properties", "target_other",
    "target_commodities",
]


def excel_date(v):
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.date().isoformat() if isinstance(v, datetime.datetime) else v.isoformat()
    try:
        return (EXCEL_EPOCH + timedelta(days=float(v))).isoformat()
    except (TypeError, ValueError):
        return ""


def read_rows(path):
    """Read the submitted_disclosures sheet. pyxlsb occasionally fails to decode
    a file's shared-string table (numbers read, strings come back None); when the
    header is missing we fall back to a LibreOffice-converted xlsx via openpyxl."""
    with open_workbook(path) as wb:
        with wb.get_sheet("submitted_disclosures") as ws:
            rows = [[c.v for c in r] for r in ws.rows()]
    if rows and "KSDSID" in [str(h) for h in rows[0]]:
        return rows
    import openpyxl
    tmp = tempfile.mkdtemp()
    subprocess.run(["soffice", "--headless", "--convert-to", "xlsx",
                    "--outdir", tmp, path], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    xlsx = os.path.join(tmp, os.path.splitext(os.path.basename(path))[0] + ".xlsx")
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    return [list(r) for r in wb["submitted_disclosures"].iter_rows(values_only=True)]


def num(v):
    if v is None or v == "":
        return ""
    try:
        return float(v)
    except (TypeError, ValueError):
        return ""


def strip_scheme_prefix(name, scheme):
    """The SAS-era XLSB names funds as "<Scheme> - <ShortName>"; the Disclose era
    and current snapshot use just <ShortName> with the scheme in its own column.
    Strip the scheme prefix so history keys (fund_name|scheme) chain across eras."""
    n = (name or "").strip()
    s = (scheme or "").strip()
    if s and n.lower().startswith(s.lower()):
        rest = n[len(s):].lstrip(" -–—")
        return rest or n
    return n


def add(a, b):
    a, b = num(a), num(b)
    if a == "" and b == "":
        return ""
    return (a or 0) + (b or 0)


def convert_file(path):
    rows = read_rows(path)
    header = [str(h) for h in rows[0]]
    idx = {h: i for i, h in enumerate(header)}

    def g(row, col):
        i = idx.get(col)
        return row[i] if i is not None and i < len(row) else None

    out = []
    for row in rows[1:]:
        if not row or g(row, "s_KSFundName") in (None, ""):
            continue
        rec = {c: "" for c in COLUMNS}
        rec["quarter"] = excel_date(g(row, "d_periodEnd"))
        rec["fund_number"] = str(g(row, "KSDSID") or "").strip()
        rec["scheme_name"] = str(g(row, "s_KSSchemeName") or "").strip()
        rec["fund_name"] = strip_scheme_prefix(str(g(row, "s_KSFundName") or ""), rec["scheme_name"])
        rec["provider"] = str(g(row, "s_KSManagerName") or "").strip()
        rec["fum"] = num(g(row, "n_totFundValue"))
        rec["members"] = num(g(row, "n_ofMembers"))
        rec["fund_start_date"] = excel_date(g(row, "d_fundStart"))
        rec["return_1yr"] = num(g(row, "p_pastYear0pir"))
        rec["fee_total"] = num(g(row, "p_totFundFees"))
        rec["alloc_cash_and_cash_equivalents"] = num(g(row, "p_actCashEquiv"))
        rec["alloc_new_zealand_fixed_interest"] = num(g(row, "p_actNZFixInt"))
        rec["alloc_international_fixed_interest"] = num(g(row, "p_actIntnatFixInt"))
        rec["alloc_australasian_equities"] = num(g(row, "p_actAustEquit"))
        rec["alloc_international_equities"] = num(g(row, "p_actIntnatEquit"))
        rec["alloc_listed_properties"] = num(g(row, "p_actListProp"))
        rec["alloc_unlisted_properties"] = num(g(row, "p_actUnlistProp"))
        rec["alloc_other"] = add(g(row, "p_actOther"), g(row, "p_actUnknown"))
        rec["target_cash_and_cash_equivalents"] = num(g(row, "p_tgtCashEquiv"))
        rec["target_new_zealand_fixed_interest"] = num(g(row, "p_tgtNZFixInt"))
        rec["target_international_fixed_interest"] = num(g(row, "p_tgtIntnatFixInt"))
        rec["target_australasian_equities"] = num(g(row, "p_tgtAustEquit"))
        rec["target_international_equities"] = num(g(row, "p_tgtIntnatEquit"))
        rec["target_listed_properties"] = num(g(row, "p_tgtListProp"))
        rec["target_unlisted_properties"] = num(g(row, "p_tgtUnlistProp"))
        rec["target_other"] = add(g(row, "p_tgtOther"), g(row, "p_tgtUnknown"))
        out.append(rec)
    return out


def main():
    files = sorted(glob.glob(os.path.join(RAW, "*.xlsb")))
    existing_quarters = set()
    with open(COMBINED, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            existing_quarters.add(r["quarter"])

    new_rows, added_quarters = [], set()
    for path in files:
        recs = convert_file(path)
        q = recs[0]["quarter"] if recs else "?"
        if q in existing_quarters:
            print(f"skip {os.path.basename(path)} ({q} already present, {len(recs)} rows)")
            continue
        new_rows.extend(recs)
        added_quarters.add(q)
        print(f"add  {os.path.basename(path)} -> {q}: {len(recs)} rows")

    if not new_rows:
        print("nothing new to add")
        return

    with open(COMBINED, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        for rec in new_rows:
            w.writerow(rec)
    print(f"\nappended {len(new_rows)} rows across quarters: {sorted(added_quarters)}")


if __name__ == "__main__":
    main()
