#!/usr/bin/env python3
"""
Comprehensive parser for ALL FMA KiwiSaver CSV files (2015-2022).
Handles 17 original CSVs + 8 converted CSVs from binary spreadsheets.
Plus the special xlsb-derived CSV with a different schema.
"""

import csv
import json
import os
import re
from datetime import datetime

RAW_DIR = '/opt/data/kiwisaver-data/raw/fma-csvs'
OUT_DIR = '/opt/data/kiwisaver-data/extracted'

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
    name = name.strip()
    name = re.sub(r'\s+', ' ', name)
    return name.lower()


def try_parse_float(val):
    if val is None:
        return None
    val = str(val).strip()
    if val == '' or val == '-' or val == 'n/a' or val == 'NULL' or val == 'null' or val == '#N/A':
        return None
    val = val.replace('%', '').replace('$', '').replace(',', '').strip()
    # Handle negative numbers in parentheses
    if val.startswith('(') and val.endswith(')'):
        val = '-' + val[1:-1]
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def try_parse_int(val):
    if val is None:
        return None
    val = str(val).strip()
    if val == '' or val == '-' or val == 'n/a' or val == 'NULL' or val == 'null':
        return None
    try:
        return int(float(val.replace(',', '')))
    except (ValueError, TypeError):
        return None


def parse_date(val):
    if not val:
        return None
    val = str(val).strip()
    
    # Handle Excel serial dates (float numbers)
    try:
        serial = float(val)
        if 40000 < serial < 60000:
            from datetime import datetime as dt, timedelta
            base = dt(1899, 12, 30)
            parsed = base + timedelta(days=serial)
            return parsed.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        pass
    
    # Strip time component if present
    if ' ' in val:
        val = val.split(' ')[0]
    
    for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%b-%y', '%d %B %Y', '%B %d, %Y', '%d-%m-%Y']:
        try:
            parsed = datetime.strptime(val, fmt)
            return parsed.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return val  # return raw if can't parse


def find_col(headers, *patterns, norm_headers=None):
    """Find column index matching any pattern. Returns None if not found."""
    norm_headers = norm_headers or [normalize_col_name(h) for h in headers]
    for p in patterns:
        p_lower = normalize_col_name(p)
        for i, nh in enumerate(norm_headers):
            if p_lower == nh:
                return i
    for p in patterns:
        p_lower = normalize_col_name(p)
        for i, nh in enumerate(norm_headers):
            if p_lower in nh:
                return i
    return None


def process_standard_csv(filepath):
    """
    Process a standard CSV file with ~161-162+ columns.
    Returns list of fund dicts, anomalies list, and period_date.
    """
    # Read file
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='latin-1') as f:
            content = f.read()

    reader = csv.reader(content.splitlines())
    headers = [next(reader)]
    # Some files have a weird first row issue - check if first row looks like data
    first_row = headers[0]
    # Normal: Fund Number, Fund Name... 
    # Abnormal: starts with a number
    if first_row and first_row[0] and first_row[0].strip().isdigit():
        # First row is actually data, not headers. Rescan.
        # Re-read properly
        reader2 = csv.reader(content.splitlines())
        headers = next(reader2)
    else:
        headers = first_row

    headers = [h.strip() for h in headers]
    norm_headers = [normalize_col_name(h) for h in headers]

    # Identify key columns
    col = {}
    
    # Fund number
    idx = find_col(headers, 'Fund Number', norm_headers=norm_headers)
    if idx is not None: col['fund_number'] = idx
    
    idx = find_col(headers, 'Fund Name', norm_headers=norm_headers)
    if idx is not None: col['fund_name'] = idx
    
    idx = find_col(headers, 'Scheme Name', norm_headers=norm_headers)
    if idx is not None: col['scheme_name'] = idx
    
    idx = find_col(headers, 'Period to which disclosure statement relates', 
                   'Period To Which Disclosure Statement Relates', norm_headers=norm_headers)
    if idx is not None: col['period_date'] = idx
    
    idx = find_col(headers, 'Value of fund as at last quarter',
                   'Value Of Fund As At Last Quarter', norm_headers=norm_headers)
    if idx is not None: col['fum'] = idx
    
    idx = find_col(headers, 'Number of members in the fund',
                   'Number Of Members In The Fund', norm_headers=norm_headers)
    if idx is not None: col['members'] = idx
    
    idx = find_col(headers, 'Date the fund started',
                   'Date The Fund Started', norm_headers=norm_headers)
    if idx is not None: col['fund_start_date'] = idx
    
    idx = find_col(headers, 'Past year return(%) net charges and tax',
                   'Past Year Return(%) Net Charges And Tax', norm_headers=norm_headers)
    if idx is not None: col['past_year_return'] = idx
    
    # Annual returns 1-10
    for i in range(1, 11):
        idx = find_col(headers, f'Annual Return % {i}', f'Annual Return %{i}',
                       f'Annual Return {i}', f'Annual Return Year {i}', norm_headers=norm_headers)
        if idx is not None: col[f'annual_return_{i}'] = idx
    
    idx = find_col(headers, 'Total Annual Fund Fees', norm_headers=norm_headers)
    if idx is not None: col['total_fees'] = idx
    
    idx = find_col(headers, "Manager's basic fee", norm_headers=norm_headers)
    if idx is not None: col['managers_basic_fee'] = idx
    
    idx = find_col(headers, 'Manager', norm_headers=norm_headers)
    if idx is not None: col['manager'] = idx
    
    idx = find_col(headers, 'Risk Reward Indicator Code', norm_headers=norm_headers)
    if idx is not None: col['risk_reward_code'] = idx
    
    idx = find_col(headers, 'Average 5 Yrs Return Net', 'Average 5 Yrs Return Net',
                   'Average 5 yr return net', norm_headers=norm_headers)
    if idx is not None: col['avg_5yr_return'] = idx
    
    idx = find_col(headers, 'Transitioning Scheme Name', norm_headers=norm_headers)
    if idx is not None: col['transitioning_scheme'] = idx

    # Build asset allocation maps
    actual_asset_cols = {}
    target_asset_cols = {}
    for cat in ASSET_CATS:
        # Try various prefix spellings
        for prefix in ['Actual investment mix: ', 'Actual Investment Mix: ']:
            a_idx = find_col(headers, prefix + cat, norm_headers=norm_headers)
            if a_idx is not None:
                actual_asset_cols[cat] = a_idx
                break
        for prefix in ['Target investment mix: ', 'Target Investment Mix: ']:
            t_idx = find_col(headers, prefix + cat, norm_headers=norm_headers)
            if t_idx is not None:
                target_asset_cols[cat] = t_idx
                break

    # Top 10 holdings columns
    top10_name_cols = {}
    top10_pct_cols = {}
    top10_type_cols = {}
    top10_country_cols = {}
    for i in range(1, 11):
        for prefix_name in [f'Top 10 Investments {i}: Name', f'Top {i} Investments: Name']:
            idx = find_col(headers, prefix_name, norm_headers=norm_headers)
            if idx is not None:
                top10_name_cols[i] = idx
                break
        for prefix_pct in [f'Top 10 Investments {i}: Percentage of fund net assets',
                          f'Top 10 Investments {i}: Percentage Of Fund Net Assets']:
            idx = find_col(headers, prefix_pct, norm_headers=norm_headers)
            if idx is not None:
                top10_pct_cols[i] = idx
                break
        for prefix_type in [f'Top 10 Investments {i}: Type']:
            idx = find_col(headers, prefix_type, norm_headers=norm_headers)
            if idx is not None:
                top10_type_cols[i] = idx
                break
        for prefix_country in [f'Top 10 Investments {i}: Country']:
            idx = find_col(headers, prefix_country, norm_headers=norm_headers)
            if idx is not None:
                top10_country_cols[i] = idx
                break

    print(f"  Columns: {len(headers)}, mapped: {list(col.keys())}")
    
    funds = []
    anomalies = []
    period_date = None

    for row in reader:
        if not row or len(row) < 5:
            continue
        
        fund = {}
        
        # Basic info
        fund['fund_number'] = str(row[col['fund_number']]).strip() if 'fund_number' in col and col['fund_number'] < len(row) else None
        fund['fund_name'] = str(row[col['fund_name']]).strip() if 'fund_name' in col and col['fund_name'] < len(row) else None
        fund['scheme_name'] = str(row[col['scheme_name']]).strip() if 'scheme_name' in col and col['scheme_name'] < len(row) else None
        
        if 'manager' in col and col['manager'] < len(row):
            val = str(row[col['manager']]).strip()
            fund['provider'] = val if val else None
        elif 'transitioning_scheme' in col:
            fund['provider'] = str(row[col['transitioning_scheme']]).strip() or None
        else:
            fund['provider'] = fund['scheme_name']
        
        # Period date
        period_raw = str(row[col['period_date']]).strip() if 'period_date' in col and col['period_date'] < len(row) else ''
        if period_raw:
            fund['period_date'] = parse_date(period_raw)
            period_date = fund['period_date']
        
        # FUM
        if 'fum' in col and col['fum'] < len(row):
            fund['fum'] = try_parse_float(row[col['fum']])
        else:
            fund['fum'] = None
        
        # Members
        if 'members' in col and col['members'] < len(row):
            fund['members'] = try_parse_int(row[col['members']])
        else:
            fund['members'] = None
        
        # Fund start date
        if 'fund_start_date' in col and col['fund_start_date'] < len(row):
            raw = str(row[col['fund_start_date']]).strip()
            fund['fund_start_date'] = parse_date(raw) if raw else None
        
        # 1-year return
        if 'past_year_return' in col and col['past_year_return'] < len(row):
            fund['1yr_return'] = try_parse_float(row[col['past_year_return']])
        
        # Annual returns 1-10
        annual_returns = {}
        for i in range(1, 11):
            key = f'annual_return_{i}'
            if key in col and col[key] < len(row):
                val = try_parse_float(row[col[key]])
                if val is not None:
                    annual_returns[f'year_{i}'] = val
        fund['annual_returns_1_10'] = annual_returns if annual_returns else None
        
        # Total fees
        if 'total_fees' in col and col['total_fees'] < len(row):
            fund['total_fees'] = try_parse_float(row[col['total_fees']])
        
        # Asset allocation - actual
        fund['asset_allocation_actual'] = {}
        for cat, idx in actual_asset_cols.items():
            if idx < len(row):
                fund['asset_allocation_actual'][cat] = try_parse_float(row[idx])
        
        # Asset allocation - target
        fund['asset_allocation_target'] = {}
        for cat, idx in target_asset_cols.items():
            if idx < len(row):
                fund['asset_allocation_target'][cat] = try_parse_float(row[idx])
        
        # Top 10 holdings
        holdings = []
        for i in range(1, 11):
            name = None
            pct = None
            typ = None
            country = None
            
            if i in top10_name_cols and top10_name_cols[i] < len(row):
                n = str(row[top10_name_cols[i]]).strip()
                name = n if n else None
            if i in top10_pct_cols and top10_pct_cols[i] < len(row):
                pct = try_parse_float(row[top10_pct_cols[i]])
            if i in top10_type_cols and top10_type_cols[i] < len(row):
                t = str(row[top10_type_cols[i]]).strip()
                typ = t if t else None
            if i in top10_country_cols and top10_country_cols[i] < len(row):
                c = str(row[top10_country_cols[i]]).strip()
                country = c if c else None
            
            if name:
                holdings.append({
                    'name': name,
                    'percentage': pct,
                    'type': typ,
                    'country': country,
                })
        fund['top_10_holdings'] = holdings if holdings else None
        
        # Risk indicator
        if 'risk_reward_code' in col and col['risk_reward_code'] < len(row):
            fund['risk_indicator'] = try_parse_int(row[col['risk_reward_code']])
        
        # Average 5yr return
        if 'avg_5yr_return' in col and col['avg_5yr_return'] < len(row):
            fund['avg_5yr_return'] = try_parse_float(row[col['avg_5yr_return']])
        
        # Source tracking
        fund['_source_file'] = os.path.basename(filepath)
        
        funds.append(fund)
        
        # Check anomalies
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


def process_xlsb_csv(filepath):
    """
    Process the xlsb-derived CSV with different column schema.
    41 cols with abbreviations.
    """
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    reader = csv.reader(content.splitlines())
    headers = [h.strip() for h in next(reader)]
    norm_headers = [normalize_col_name(h) for h in headers]
    
    print(f"  Columns: {len(headers)} (xlsb format)")
    print(f"  Headers: {headers}")
    
    col = {}
    
    for i, h in enumerate(headers):
        nh = norm_headers[i]
        if nh == 'ksdsid': col['fund_number'] = i
        elif nh == 's_ksfundname': col['fund_name'] = i
        elif nh == 's_ksschemename': col['scheme_name'] = i
        elif nh == 's_ksmanagername': col['manager'] = i
        elif nh == 'd_periodend': col['period_date'] = i
        elif nh == 'd_fundstart': col['fund_start_date'] = i
        elif nh == 'n_totfundvalue': col['fum'] = i
        elif nh == 'n_ofmembers': col['members'] = i
        elif nh == 'n_membershipfees': col['membership_fees'] = i
        elif nh == 'p_totfundfees': col['total_fees'] = i
        elif nh == 'p_annmgtfee': col['managers_basic_fee'] = i
        elif nh == 'p_performfees': col['performance_fees'] = i
        elif nh == 'p_otherfeescosts': col['other_fees'] = i
        elif nh == 'p_pastyear0pir': col['1yr_return'] = i   # past year return - 0 PIR
        elif nh == 'p_pastyearhighpir': col['1yr_return_high'] = i
        elif nh == 'p_past3mth0pir': col['3mth_return'] = i
        elif nh == 'p_past3mthhighpir': col['3mth_return_high'] = i
        elif nh == 'n_tottop10assets': col['total_top10_assets'] = i
    
    print(f"  Mapped columns: {list(col.keys())}")
    
    # Asset allocation mappings
    # xlsb: p_actCashEquiv, p_actNZFixInt, p_actIntnatFixInt, p_actAustEquit,
    #       p_actIntnatEquit, p_actListProp, p_actUnlistProp, p_actUnknown, p_actOther
    # Target: p_tgtCashEquiv, etc.
    xlsb_to_cat = {
        'p_actcashequiv': 'Cash and cash equivalents',
        'p_actnzfixint': 'New Zealand fixed interest',
        'p_actintnatfixint': 'International fixed interest',
        'p_actaustequit': 'Australasian equities',
        'p_actintnatequit': 'International equities',
        'p_actlistprop': 'Listed Properties',
        'p_actunlistprop': 'Unlisted Properties',
        'p_actunknown': 'Unknown',
        'p_actother': 'Other',
    }
    xlsb_to_cat_target = {}
    for k, v in xlsb_to_cat.items():
        xlsb_to_cat_target[k.replace('act', 'tgt')] = v
    
    funds = []
    anomalies = []
    period_date = None
    
    for row in reader:
        if not row or len(row) < 5:
            continue
        
        fund = {}
        
        fund['fund_number'] = str(row[col.get('fund_number', 0)]).strip() if col.get('fund_number', 0) < len(row) else None
        fund['fund_name'] = str(row[col.get('fund_name', 1)]).strip() if col.get('fund_name', 1) < len(row) else None
        fund['scheme_name'] = str(row[col.get('scheme_name', 2)]).strip() if col.get('scheme_name', 2) < len(row) else None
        fund['provider'] = str(row[col.get('manager', 3)]).strip() if col.get('manager', 3) < len(row) else None
        
        if 'period_date' in col and col['period_date'] < len(row):
            raw = str(row[col['period_date']]).strip()
            fund['period_date'] = parse_date(raw)
            period_date = fund['period_date']
        
        if 'fund_start_date' in col and col['fund_start_date'] < len(row):
            raw = str(row[col['fund_start_date']]).strip()
            fund['fund_start_date'] = parse_date(raw) if raw else None
        
        fund['fum'] = try_parse_float(row[col['fum']]) if 'fum' in col and col['fum'] < len(row) else None
        fund['members'] = try_parse_int(row[col['members']]) if 'members' in col and col['members'] < len(row) else None
        fund['1yr_return'] = try_parse_float(row[col['1yr_return']]) if '1yr_return' in col and col['1yr_return'] < len(row) else None
        fund['total_fees'] = try_parse_float(row[col['total_fees']]) if 'total_fees' in col and col['total_fees'] < len(row) else None
        
        # XLSB-specific fields
        fund['1yr_return_high_pir'] = try_parse_float(row[col['1yr_return_high']]) if '1yr_return_high' in col and col['1yr_return_high'] < len(row) else None
        fund['membership_fees'] = try_parse_float(row[col['membership_fees']]) if 'membership_fees' in col and col['membership_fees'] < len(row) else None
        fund['managers_basic_fee'] = try_parse_float(row[col['managers_basic_fee']]) if 'managers_basic_fee' in col and col['managers_basic_fee'] < len(row) else None
        fund['performance_fees'] = try_parse_float(row[col['performance_fees']]) if 'performance_fees' in col and col['performance_fees'] < len(row) else None
        fund['other_fees'] = try_parse_float(row[col['other_fees']]) if 'other_fees' in col and col['other_fees'] < len(row) else None
        fund['total_top10_assets_pct'] = try_parse_float(row[col['total_top10_assets']]) if 'total_top10_assets' in col and col['total_top10_assets'] < len(row) else None
        
        # Asset allocation
        fund['asset_allocation_actual'] = {}
        fund['asset_allocation_target'] = {}
        for nh_key, cat in xlsb_to_cat.items():
            for i, h in enumerate(headers):
                if normalize_col_name(h) == nh_key:
                    fund['asset_allocation_actual'][cat] = try_parse_float(row[i]) if i < len(row) else None
                    break
        for nh_key, cat in xlsb_to_cat_target.items():
            for i, h in enumerate(headers):
                if normalize_col_name(h) == nh_key:
                    fund['asset_allocation_target'][cat] = try_parse_float(row[i]) if i < len(row) else None
                    break
        
        fund['annual_returns_1_10'] = None  # Not available in xlsb format
        fund['top_10_holdings'] = None
        fund['risk_indicator'] = None
        fund['avg_5yr_return'] = None
        
        fund['_source_file'] = os.path.basename(filepath)
        fund['_xlsb_format'] = True
        
        funds.append(fund)
        
        if fund.get('1yr_return') is not None and (fund['1yr_return'] > 40 or fund['1yr_return'] < -40):
            anomalies.append({
                'fund_number': fund['fund_number'],
                'fund_name': fund['fund_name'],
                'period_date': fund.get('period_date'),
                'field': '1yr_return',
                'value': fund['1yr_return']
            })
    
    print(f"  Parsed {len(funds)} funds, found {len(anomalies)} anomalous returns")
    return funds, anomalies, period_date


def process_file(filepath, label_date=None):
    """Route file to appropriate processor."""
    filename = os.path.basename(filepath)
    
    # Detect xlsb-derived format by checking headers
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        header = f.readline().strip()
    
    is_xlsb_format = 's_KSFundName' in header or 'KSDSID' in header
    
    if is_xlsb_format:
        return process_xlsb_csv(filepath)
    else:
        return process_standard_csv(filepath)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    
    # Collect ALL CSV files (original + converted)
    all_csv_files = []
    for f in os.listdir(RAW_DIR):
        if f.endswith('.csv') and not f.endswith('.converted.csv') and not f.endswith('.error.txt'):
            all_csv_files.append(f)
    # Add converted files
    for f in os.listdir(RAW_DIR):
        if f.endswith('.converted.csv'):
            all_csv_files.append(f)
    
    all_csv_files.sort()
    print(f"Found {len(all_csv_files)} CSV files to process")
    
    # Manual date mappings for files where period date can't be extracted from content
    date_overrides = {
        '150930-Disclose-Register-KiwiSaver-fund-updates-for-30-September-2015.xls.converted.csv': '2015-09-30',
        '151231-Disclose-Register-Kiwisaver-fund-updates-for-31-December-2015.xls.converted.csv': '2015-12-31',
        'Disclose-Register-Kiwisaver-fund-updates-for-31-March-2016.xlsx.converted.csv': '2016-03-31',
        'Disclose-Register-Kiwisaver-fund-updates-for-30-June-2016.xls.converted.csv': '2016-06-30',
        'Disclose-Register-Kiwisaver-fund-updates-for-30-September-2016..xls.converted.csv': '2016-09-30',
        'Disclose-Register-Kiwisaver-fund-updates-for-31-December-2016.xlsx.converted.csv': '2016-12-31',
        'FMA-KDS-WEB-Quarterly-20151231.xlsb.converted.csv': '2015-12-31',
    }
    
    all_funds = []
    all_anomalies = []
    all_funds_by_file = []
    all_period_dates = set()
    
    for filename in all_csv_files:
        filepath = os.path.join(RAW_DIR, filename)
        print(f"\nProcessing: {filename}")
        
        try:
            funds, anomalies, period_date = process_file(filepath)
            
            # Use override if available and period_date wasn't extracted
            if not period_date and filename in date_overrides:
                period_date = date_overrides[filename]
            
            if not period_date and filename in date_overrides:
                period_date = date_overrides[filename]
            
            # If still no period_date, try to extract from filename
            if not period_date:
                # Try to extract date from filename
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
                if date_match:
                    period_date = date_match.group(1)
                else:
                    # Try other patterns
                    for pattern in ['30-September-2015', '31-December-2015', '31-March-2016',
                                    '30-June-2016', '30-September-2016', '31-December-2016',
                                    '31-December-2022']:
                        if pattern in filename:
                            parts = pattern.split('-')
                            month_map = {
                                'January': '01', 'February': '02', 'March': '03',
                                'April': '04', 'May': '05', 'June': '06',
                                'July': '07', 'August': '08', 'September': '09',
                                'October': '10', 'November': '11', 'December': '12'
                            }
                            day = parts[0]
                            month = month_map.get(parts[1], '01')
                            year = parts[2]
                            period_date = f'{year}-{month}-{day}'
                            break
            
            if period_date:
                all_period_dates.add(period_date)
            
            # Set period_date for funds that don't have one
            for fund in funds:
                if not fund.get('period_date') and period_date:
                    fund['period_date'] = period_date
            
            all_funds.extend(funds)
            all_anomalies.extend(anomalies)
            all_funds_by_file.append((period_date or 'unknown', funds))
            
            # Save individual file
            safe_date = period_date or f'unknown_{filename[:20]}'
            out_filename = f'fma_csv_{safe_date}.json'
            out_path = os.path.join(OUT_DIR, out_filename)
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(funds, f, indent=2, default=str)
            print(f"  Saved {len(funds)} funds to {out_path}")
            
        except Exception as e:
            print(f"  ERROR processing {filename}: {e}")
            import traceback
            traceback.print_exc()
    
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
    
    # Report periods covered
    print(f"\n=== PERIODS COVERED ===")
    for d in sorted(all_period_dates):
        print(f"  {d}")
    
    print(f"\nDone! Total funds parsed: {len(all_funds)}")
    print(f"Total anomalous returns: {len(all_anomalies)}")


if __name__ == '__main__':
    main()
