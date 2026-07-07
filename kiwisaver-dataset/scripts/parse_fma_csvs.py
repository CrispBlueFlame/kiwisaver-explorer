#!/usr/bin/env python3
"""
Parse FMA KiwiSaver CSV files into structured JSON.
Handles 4 files with different column structures.
"""

import csv
import json
import os
import re
import sys
from datetime import datetime

# Source directory
RAW_DIR = os.path.join('/opt/data/kiwisaver-data', 'raw', 'fma-csvs')
OUT_DIR = os.path.join('/opt/data/kiwisaver-data', 'extracted')

# Files to process: (filepath, label_date)
FILES = [
    ('311221-Disclose-Register-KiwiSaver-fund-update.csv', '2021-12-31'),
    ('Disclose-Register-KiwiSaver-fund-updates-for-31-March-2020.csv', '2020-03-31'),
    ('Disclose-Register-KiwiSaver-fund-updates-for-31-December-2017.csv', '2017-12-31'),
    ('30-September-2021-Disclose-Register-KiwiSaver-fund-updates.csv', '2021-09-30'),
]

# Files that have a dedicated "Manager" column (separate from "Manager's basic fee")
FILES_WITH_MANAGER_COL = {'30-September-2021-Disclose-Register-KiwiSaver-fund-updates.csv'}

# Asset allocation categories (10)
ASSET_CATS = [
    'Cash and cash equivalents',
    'New Zealand fixed interest',
    'International fixed interest',
    'Australasian equities',
    'International equities',
    'Listed Properties',
    'Unlisted Properties',
    'Unknown',
    'Other',
    'Commodities',
]


def normalize_col_name(name):
    """Normalize column name to a canonical form for matching."""
    name = name.strip()
    # Normalize whitespace
    name = re.sub(r'\s+', ' ', name)
    # Lowercase for comparison
    return name.lower()


def find_col_mapping(headers, known_mappings):
    """
    Build column index mapping by normalizing headers and matching against
    known pattern dictionaries.
    known_mappings: list of (canonical_name, patterns_or_exact) where
                    each element is (canonical_name, [patterns], exact_flag)
                    If exact_flag is True, patterns must match exactly (after normalize).
                    If False, substring match.
    Returns dict mapping canonical_name -> column_index
    """
    norm_headers = [(i, h.strip(), normalize_col_name(h.strip())) for i, h in enumerate(headers)]

    mapping = {}
    for entry in known_mappings:
        if len(entry) == 3:
            canonical_name, patterns, exact = entry
        else:
            canonical_name, patterns = entry
            exact = False

        for idx, raw_h, norm_h in norm_headers:
            for pattern in patterns:
                norm_pattern = normalize_col_name(pattern)
                if exact:
                    if norm_h == norm_pattern:
                        mapping[canonical_name] = idx
                        break
                else:
                    if norm_pattern in norm_h:
                        mapping[canonical_name] = idx
                        break
            if canonical_name in mapping:
                break

    return mapping


def try_parse_float(val):
    """Try to parse a value as float, return None if not possible."""
    if val is None:
        return None
    val = val.strip()
    if val == '' or val == '-' or val == 'n/a' or val == 'NULL' or val == 'null':
        return None
    # Remove % sign
    val = val.replace('%', '').strip()
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def try_parse_int(val):
    """Try to parse a value as int."""
    if val is None:
        return None
    val = val.strip()
    if val == '' or val == '-' or val == 'n/a' or val == 'NULL' or val == 'null':
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def extract_top_10_holdings(row, headers, col_map):
    """Extract top 10 holdings from row."""
    holdings = []
    for i in range(1, 11):
        name = None
        pct = None
        typ = None
        country = None

        # Try different column naming conventions
        for col_name_base in [f'Top 10 Investments {i}: Name', f'Top 10 Investments {i}: Name']:
            for h_idx, h in enumerate(headers):
                nh = normalize_col_name(h)
                base_norm = normalize_col_name(col_name_base)
                if base_norm == nh:
                    name = row[h_idx].strip() if h_idx < len(row) else None
                    break
            if name:
                break

        # Find percentage
        for h_idx, h in enumerate(headers):
            nh = normalize_col_name(h)
            if f'top 10 investments {i}:' in nh and ('percentage' in nh or 'net assets' in nh):
                pct = try_parse_float(row[h_idx]) if h_idx < len(row) else None
                break

        # Find type
        for h_idx, h in enumerate(headers):
            nh = normalize_col_name(h)
            m = re.match(r'top 10 investments (\d+):\s*type', nh)
            if m and int(m.group(1)) == i:
                typ = row[h_idx].strip() if h_idx < len(row) else None
                break

        # Find country
        for h_idx, h in enumerate(headers):
            nh = normalize_col_name(h)
            m = re.match(r'top 10 investments (\d+):\s*country', nh)
            if m and int(m.group(1)) == i:
                country = row[h_idx].strip() if h_idx < len(row) else None
                break

        if name and name.strip():
            holdings.append({
                'name': name.strip(),
                'percentage': pct,
                'type': typ.strip() if typ else None,
                'country': country.strip() if country else None,
            })
    return holdings


def extract_asset_allocation(row, headers, prefix):
    """
    Extract asset allocation for all 10 categories.
    prefix: 'Actual investment mix: ' or 'Target investment mix: '
    """
    allocation = {}
    norm_headers = [(i, h.strip(), normalize_col_name(h.strip())) for i, h in enumerate(headers)]
    prefix_norm = normalize_col_name(prefix)

    for cat in ASSET_CATS:
        search = normalize_col_name(prefix + cat)
        for idx, raw_h, norm_h in norm_headers:
            if norm_h == search:
                val = try_parse_float(row[idx]) if idx < len(row) else None
                allocation[cat] = val
                break

    return allocation


def process_csv(filepath, label_date):
    """Process a single CSV file and return list of fund dicts."""
    filename = os.path.basename(filepath)
    has_manager_col = filename in FILES_WITH_MANAGER_COL
    funds = []
    anomalies = []
    period_date = label_date  # default

    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='latin-1') as f:
            content = f.read()

    # Parse CSV
    reader = csv.reader(content.splitlines())
    headers = [h.strip() for h in next(reader)]
    norm_headers = [normalize_col_name(h) for h in headers]

    print(f"  File: {os.path.basename(filepath)}")
    print(f"  Columns: {len(headers)}")

    # Build column mapping - only look for Manager column if the file has one
    # Files without it have "Manager's basic fee" which would falsely match
    known_mappings = [
        ('fund_number', ['Fund Number']),
        ('fund_name', ['Fund Name']),
        ('scheme_name', ['Scheme Name']),
        ('period_date', ['Period to which disclosure statement relates',
                         'Period To Which Disclosure Statement Relates']),
        ('fum', ['Value of fund as at last quarter', 'Value Of Fund As At Last Quarter']),
        ('members', ['Number of members in the fund', 'Number Of Members In The Fund']),
        ('fund_start_date', ['Date the fund started', 'Date The Fund Started']),
        ('past_year_return', ['Past year return(%) net charges and tax',
                               'Past Year Return(%) Net Charges And Tax']),
        ('annual_return_pct_1', ['Annual Return % 1', 'Annual Return %1']),
        ('annual_return_pct_2', ['Annual Return % 2', 'Annual Return %2']),
        ('annual_return_pct_3', ['Annual Return % 3', 'Annual Return %3']),
        ('annual_return_pct_4', ['Annual Return % 4', 'Annual Return %4']),
        ('annual_return_pct_5', ['Annual Return % 5', 'Annual Return %5']),
        ('annual_return_pct_6', ['Annual Return % 6', 'Annual Return %6']),
        ('annual_return_pct_7', ['Annual Return % 7', 'Annual Return %7']),
        ('annual_return_pct_8', ['Annual Return % 8', 'Annual Return %8']),
        ('annual_return_pct_9', ['Annual Return % 9', 'Annual Return %9']),
        ('annual_return_pct_10', ['Annual Return % 10', 'Annual Return %10']),
        ('total_fees', ['Total Annual Fund Fees']),
        ('managers_basic_fee', ["Manager's basic fee", "Manager's Basic Fee"]),
    ]

    if has_manager_col:
        known_mappings.extend([
            ('manager', ['Manager'], True),  # exact match to avoid "Manager's Basic Fee"
            ('risk_reward_code', ['Risk Reward Indicator Code']),
            ('avg_5yr_return', ['Average 5 Yrs Return Net', 'Average 5 Year Return Net']),
        ])

    col_map = find_col_mapping(headers, known_mappings)

    print(f"  Found key columns: {list(col_map.keys())}")

    row_count = 0
    for row in reader:
        if not row or len(row) < 5:
            continue
        row_count += 1

        fund = {}

        # Basic info
        fund['fund_number'] = row[col_map.get('fund_number', 0)].strip() if col_map.get('fund_number', 0) < len(row) else None
        fund['fund_name'] = row[col_map.get('fund_name', 1)].strip() if col_map.get('fund_name', 1) < len(row) else None
        fund['scheme_name'] = row[col_map.get('scheme_name', 10)].strip() if col_map.get('scheme_name', 10) < len(row) else None

        # Manager/provider - use 'Manager' column if available, otherwise from scheme info
        if 'manager' in col_map:
            fund['provider'] = row[col_map['manager']].strip() if col_map['manager'] < len(row) else None
        else:
            # Infer from Scheme Name or Transitioning Scheme Name
            fund['provider'] = fund['scheme_name']

        # Period date
        if 'period_date' in col_map and col_map['period_date'] < len(row):
            raw_date = row[col_map['period_date']].strip()
            if raw_date:
                # Handle different date formats
                for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%b-%y']:
                    try:
                        parsed = datetime.strptime(raw_date, fmt)
                        fund['period_date'] = parsed.strftime('%Y-%m-%d')
                        period_date = fund['period_date']
                        break
                    except ValueError:
                        continue
                if 'period_date' not in fund:
                    fund['period_date'] = raw_date
            else:
                fund['period_date'] = label_date
        else:
            fund['period_date'] = label_date

        # FUM
        if 'fum' in col_map and col_map['fum'] < len(row):
            raw_fum = row[col_map['fum']].strip()
            fund['fum'] = try_parse_float(raw_fum)

        # Members
        if 'members' in col_map and col_map['members'] < len(row):
            fund['members'] = try_parse_int(row[col_map['members']])

        # Fund start date
        if 'fund_start_date' in col_map and col_map['fund_start_date'] < len(row):
            raw = row[col_map['fund_start_date']].strip()
            if raw:
                for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%b-%y']:
                    try:
                        parsed = datetime.strptime(raw, fmt)
                        fund['fund_start_date'] = parsed.strftime('%Y-%m-%d')
                        break
                    except ValueError:
                        continue
                if 'fund_start_date' not in fund:
                    fund['fund_start_date'] = raw

        # Past year return (1yr)
        if 'past_year_return' in col_map and col_map['past_year_return'] < len(row):
            fund['1yr_return'] = try_parse_float(row[col_map['past_year_return']])

        # Annual returns 1-10 (individual year returns)
        annual_returns = {}
        for i in range(1, 11):
            key = f'annual_return_pct_{i}'
            if key in col_map and col_map[key] < len(row):
                val = try_parse_float(row[col_map[key]])
                if val is not None:
                    annual_returns[f'year_{i}'] = val
        fund['annual_returns_1_10'] = annual_returns if annual_returns else None

        # Fees
        if 'total_fees' in col_map and col_map['total_fees'] < len(row):
            fund['total_fees'] = try_parse_float(row[col_map['total_fees']])

        # Asset allocation - actual
        fund['asset_allocation_actual'] = extract_asset_allocation(row, headers, 'Actual investment mix: ')

        # Asset allocation - target
        fund['asset_allocation_target'] = extract_asset_allocation(row, headers, 'Target investment mix: ')

        # Top 10 holdings
        fund['top_10_holdings'] = extract_top_10_holdings(row, headers, col_map)

        # Risk reward indicator
        if 'risk_reward_code' in col_map and col_map['risk_reward_code'] < len(row):
            fund['risk_indicator'] = try_parse_int(row[col_map['risk_reward_code']])

        # Average 5yr return
        if 'avg_5yr_return' in col_map and col_map['avg_5yr_return'] < len(row):
            fund['avg_5yr_return'] = try_parse_float(row[col_map['avg_5yr_return']])

        # Source file tracking
        fund['_source_file'] = os.path.basename(filepath)

        funds.append(fund)

        # Check for anomalous returns
        if fund.get('1yr_return') is not None:
            if fund['1yr_return'] > 40 or fund['1yr_return'] < -40:
                anomalies.append({
                    'fund_number': fund['fund_number'],
                    'fund_name': fund['fund_name'],
                    'period_date': fund.get('period_date'),
                    'field': '1yr_return',
                    'value': fund['1yr_return']
                })

        if fund.get('annual_returns_1_10'):
            for yr_key, yr_val in fund['annual_returns_1_10'].items():
                if yr_val is not None and (yr_val > 40 or yr_val < -40):
                    anomalies.append({
                        'fund_number': fund['fund_number'],
                        'fund_name': fund['fund_name'],
                        'period_date': fund.get('period_date'),
                        'field': f'annual_return_{yr_key}',
                        'value': yr_val
                    })

    print(f"  Parsed {len(funds)} funds, found {len(anomalies)} anomalous returns")
    return funds, anomalies, period_date


def find_fund_name_changes(all_funds_by_file):
    """Compare fund names across files to detect name changes."""
    # Build mapping of fund_number -> { file -> fund_name }
    fund_names = {}  # fund_number -> { source -> name }
    for file_label, funds in all_funds_by_file:
        for f in funds:
            fn = f.get('fund_number')
            if fn:
                if fn not in fund_names:
                    fund_names[fn] = {}
                fund_names[fn][file_label] = f.get('fund_name', '')

    changes = []
    for fn, names_by_file in fund_names.items():
        unique_names = set(n for n in names_by_file.values() if n)
        if len(unique_names) > 1:
            changes.append({
                'fund_number': fn,
                'name_changes': dict(sorted(names_by_file.items()))
            })

    return changes


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    all_funds = []
    all_anomalies = []
    all_funds_by_file = []

    for filename, label_date in FILES:
        filepath = os.path.join(RAW_DIR, filename)
        if not os.path.exists(filepath):
            print(f"WARNING: File not found: {filepath}")
            continue

        print(f"\nProcessing: {filename}")
        funds, anomalies, period_date = process_csv(filepath, label_date)
        all_funds.extend(funds)
        all_anomalies.extend(anomalies)
        all_funds_by_file.append((period_date, funds))

        # Save individual file
        out_filename = f'fma_csv_{period_date}.json'
        out_path = os.path.join(OUT_DIR, out_filename)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(funds, f, indent=2, default=str)
        print(f"  Saved {len(funds)} funds to {out_path}")

    # Save combined
    combined_path = os.path.join(OUT_DIR, 'fma_csv_combined.json')
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(all_funds, f, indent=2, default=str)
    print(f"\nSaved combined {len(all_funds)} funds to {combined_path}")

    # Report anomalies
    if all_anomalies:
        print(f"\n=== ANOMALOUS RETURNS (>40% or <-40%) ===")
        for a in sorted(all_anomalies, key=lambda x: abs(x['value']), reverse=True):
            print(f"  {a['fund_number']} ({a['fund_name']}) [{a['period_date']}] "
                  f"{a['field']} = {a['value']}%")

    # Find fund name changes
    name_changes = find_fund_name_changes(all_funds_by_file)
    if name_changes:
        print(f"\n=== FUND NAME CHANGES ACROSS FILES ===")
        for c in sorted(name_changes, key=lambda x: x['fund_number']):
            print(f"  {c['fund_number']}:")
            for file_label, name in c['name_changes'].items():
                print(f"    {file_label}: {name}")

    print(f"\nDone! Total funds parsed: {len(all_funds)}")
    print(f"Total anomalous returns: {len(all_anomalies)}")
    print(f"Fund name changes detected: {len(name_changes)}")


if __name__ == '__main__':
    main()
