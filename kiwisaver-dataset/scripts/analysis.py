#!/usr/bin/env python3
"""
KiwiSaver data analysis suite.
Each analysis is a standalone function. Re-run when new data arrives.
Output: /documents/Hermes/kiwisaver-analysis/*.csv
"""

import json, csv, os, sys
from collections import Counter, defaultdict
from datetime import datetime
import statistics

OUTDIR = "/documents/Hermes/kiwisaver-analysis"
DATADIR = "/opt/data/kiwisaver-data"

def load_data():
    """Load all data sources. Returns dict. Add new sources here."""
    data = {}
    
    # FMA quarterly fund data
    with open(f"{DATADIR}/extracted/fma_csv_combined.json") as f:
        data['fma'] = json.load(f)
    
    # Smart Investor current snapshot
    with open(f"{DATADIR}/extracted/smart_investor_raw.json") as f:
        si = json.load(f)
        data['smart_investor'] = si.get('funds', [])
    
    # Annual reports summary
    reports = []
    for fn in sorted(os.listdir(f"{DATADIR}/extracted/")):
        if fn.startswith('fma_report_') and fn.endswith('.json'):
            year = fn.split('_')[-1].split('.')[0]
            with open(f"{DATADIR}/extracted/{fn}") as f:
                reports.append({'year': year, 'data': json.load(f)})
    data['reports'] = reports
    
    print(f"Loaded: {len(data['fma'])} FMA records, {len(data['smart_investor'])} Smart Investor funds, {len(reports)} annual reports")
    return data

def save_csv(filename, headers, rows):
    """Save analysis to CSV."""
    os.makedirs(OUTDIR, exist_ok=True)
    path = f"{OUTDIR}/{filename}"
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  -> {path} ({len(rows)} rows)")
    return path

def safe_float(v):
    try: return float(v) if v not in (None, '', 'NULL') else None
    except: return None

def safe_int(v):
    try: return int(float(v)) if v not in (None, '', 'NULL') else None
    except: return None

# ===== ANALYSIS 1: Fee vs Return Impact =====
def analyze_fees_vs_returns(data):
    print("\n=== 1. Fee Impact Analysis ===")
    records = data['fma']
    
    # Per-provider averages
    provider_stats = defaultdict(lambda: {'fees': [], 'returns_1yr': [], 'returns_5yr': [], 'funds': set()})
    for r in records:
        prov = r.get('provider', 'Unknown')
        fee = safe_float(r.get('total_fees'))
        ret1 = safe_float(r.get('1yr_return'))
        ret5 = safe_float(r.get('avg_5yr_return'))
        fn = r.get('fund_name', '')
        
        if fee is not None:
            provider_stats[prov]['fees'].append(fee)
            provider_stats[prov]['funds'].add(fn)
        if ret1 is not None:
            provider_stats[prov]['returns_1yr'].append(ret1)
        if ret5 is not None:
            provider_stats[prov]['returns_5yr'].append(ret5)
    
    rows = []
    for prov, s in sorted(provider_stats.items()):
        if len(s['funds']) < 2:
            continue
        avg_fee = round(statistics.mean(s['fees']), 3)
        avg_ret1 = round(statistics.mean(s['returns_1yr']), 2) if s['returns_1yr'] else None
        avg_ret5 = round(statistics.mean(s['returns_5yr']), 2) if s['returns_5yr'] else None
        rows.append([prov, len(s['funds']), avg_fee, avg_ret1, avg_ret5])
    
    headers = ['Provider', 'Funds', 'Avg Fee %', 'Avg 1yr Return %', 'Avg 5yr Return %']
    save_csv('01-fee-vs-return-by-provider.csv', headers, rows)
    
    # By fund type
    type_stats = defaultdict(lambda: {'fees': [], 'returns_1yr': [], 'returns_5yr': []})
    for r in records:
        t = str(r.get('risk_indicator', 'Unknown') or '')
        fee = safe_float(r.get('total_fees'))
        ret1 = safe_float(r.get('1yr_return'))
        ret5 = safe_float(r.get('avg_5yr_return'))
        if fee: type_stats[t]['fees'].append(fee)
        if ret1: type_stats[t]['returns_1yr'].append(ret1)
        if ret5: type_stats[t]['returns_5yr'].append(ret5)
    
    rows2 = []
    for t, s in sorted(type_stats.items()):
        rows2.append([t, len(s['fees']),
            round(statistics.mean(s['fees']), 3),
            round(statistics.mean(s['returns_1yr']), 2) if s['returns_1yr'] else None,
            round(statistics.mean(s['returns_5yr']), 2) if s['returns_5yr'] else None])
    
    save_csv('01-fee-vs-return-by-risk.csv', ['Risk', 'Records', 'Avg Fee %', 'Avg 1yr Return %', 'Avg 5yr Return %'], rows2)
    return {'by_provider': rows, 'by_risk': rows2}

# ===== ANALYSIS 2: Risk vs Reward by Fund Type =====
def analyze_risk_reward(data):
    print("\n=== 2. Risk/Reward by Fund Type ===")
    records = data['fma']
    
    # Map fund types from names + risk indicator
    # We'll use risk_indicator (1-7) as our risk measure
    # and calculate actual return volatility
    
    # Group by risk indicator AND fund name to get time series
    fund_series = defaultdict(lambda: {'returns': [], 'fees': [], 'periods': []})
    for r in records:
        key = (r.get('fund_name',''), r.get('provider',''))
        ret1 = safe_float(r.get('1yr_return'))
        risk = safe_int(r.get('risk_indicator'))
        if ret1 is not None:
            fund_series[key]['returns'].append(ret1)
            fund_series[key]['periods'].append(r.get('period_date',''))
        if risk is not None:
            fund_series[key]['risk'] = risk
    
    # Calculate per-fund stats
    fund_stats = []
    for (fname, prov), s in fund_series.items():
        if len(s['returns']) < 2: continue
        avg_ret = round(statistics.mean(s['returns']), 2)
        vol = round(statistics.stdev(s['returns']), 2) if len(s['returns']) > 1 else 0
        sharpe = round(avg_ret / vol, 2) if vol > 0 else 0
        risk = s.get('risk', None)
        fund_stats.append([fname, prov, risk, len(s['returns']), avg_ret, vol, sharpe])
    
    # Sort by volatility descending
    fund_stats.sort(key=lambda x: x[5], reverse=True)
    
    # By risk indicator group
    risk_groups = defaultdict(lambda: {'returns': [], 'vols': []})
    for f in fund_stats:
        r = f[2]  # risk indicator
        if r:
            risk_groups[r]['returns'].append(f[4])
            risk_groups[r]['vols'].append(f[5])
    
    rows = []
    for r in sorted(risk_groups.keys()):
        sg = risk_groups[r]
        rows.append([r, len(sg['returns']),
            round(statistics.mean(sg['returns']), 2),
            round(statistics.mean(sg['vols']), 2)])
    
    save_csv('02-risk-reward-by-indicator.csv', ['Risk(1-7)', 'Funds', 'Avg Return %', 'Avg Volatility (std)'], rows)
    
    # Full fund-level data
    headers = ['Fund Name', 'Provider', 'Risk Indicator', 'Periods', 'Avg Return %', 'Volatility (std)', 'Return/Vol Ratio']
    save_csv('02-risk-reward-fund-detail.csv', headers, fund_stats)
    
    return {'by_risk': rows, 'fund_detail': fund_stats}

# ===== ANALYSIS 3: Performance Persistence =====
def analyze_performance_persistence(data):
    print("\n=== 3. Performance Persistence ===")
    records = data['fma']
    
    # Group returns by period
    by_period = defaultdict(list)
    for r in records:
        ret1 = safe_float(r.get('1yr_return'))
        if ret1 is not None:
            by_period[r.get('period_date','')].append({
                'fund': r.get('fund_name',''),
                'provider': r.get('provider',''),
                'return': ret1
            })
    
    # Rank funds within each period
    ranked = {}
    for period, funds in sorted(by_period.items()):
        if len(funds) < 5: continue
        sorted_funds = sorted(funds, key=lambda x: x['return'], reverse=True)
        total = len(sorted_funds)
        ranked[period] = {}
        for i, f in enumerate(sorted_funds):
            key = f"{f['provider']} - {f['fund']}"
            ranked[period][key] = i / total  # percentile rank (0=best)
    
    # Track which funds were top-quartile in consecutive periods
    periods = sorted(ranked.keys())
    persistence_data = []
    
    for i in range(len(periods) - 1):
        p1, p2 = periods[i], periods[i+1]
        common = set(ranked[p1].keys()) & set(ranked[p2].keys())
        
        for key in common:
            r1, r2 = ranked[p1][key], ranked[p2][key]
            top1 = r1 <= 0.25
            top2 = r2 <= 0.25
            bottom1 = r1 >= 0.75
            bottom2 = r2 >= 0.75
            
            if top1 and top2:
                persistence_data.append([p1, p2, key.split(' - ')[0], key.split(' - ')[1], 'Top-to-Top'])
            elif bottom1 and bottom2:
                persistence_data.append([p1, p2, key.split(' - ')[0], key.split(' - ')[1], 'Bottom-to-Bottom'])
    
    # Count persistence by type
    type_counts = Counter(r[4] for r in persistence_data)
    total_pairs = len(persistence_data)
    
    summary_rows = []
    for t, c in sorted(type_counts.items()):
        summary_rows.append([t, c, round(c/total_pairs*100, 1) if total_pairs else 0])
    save_csv('03-persistence-summary.csv', ['Persistence Type', 'Count', '% of All'], summary_rows)
    
    if persistence_data:
        save_csv('03-persistence-detail.csv', ['From Period', 'To Period', 'Provider', 'Fund', 'Persistence Type'], persistence_data[:1000])
    
    return {'summary': summary_rows, 'total_pairs': total_pairs}

# ===== ANALYSIS 4: Provider Market Overview =====
def analyze_providers(data):
    print("\n=== 4. Provider Market Overview ===")
    records = data['fma']
    
    # Latest period data for market snapshot
    periods = sorted(set(r.get('period_date','') for r in records))
    latest = periods[-1] if periods else None
    
    if not latest:
        return {'error': 'No period data'}
    
    latest_records = [r for r in records if r.get('period_date') == latest]
    
    # Aggregate by provider
    provider_summary = defaultdict(lambda: {'total_fum': 0, 'total_members': 0, 'fees': [], 'returns': [], 'fund_names': set(), 'start_dates': []})
    
    for r in latest_records:
        prov = r.get('provider', 'Unknown')
        fum = safe_float(r.get('fum'))
        mem = safe_int(r.get('members'))
        fee = safe_float(r.get('total_fees'))
        ret1 = safe_float(r.get('1yr_return'))
        
        if fum: provider_summary[prov]['total_fum'] += fum
        if mem: provider_summary[prov]['total_members'] += mem
        if fee: provider_summary[prov]['fees'].append(fee)
        if ret1 is not None: provider_summary[prov]['returns'].append(ret1)
        provider_summary[prov]['fund_names'].add(r.get('fund_name',''))
        sd = r.get('fund_start_date','')
        if sd: provider_summary[prov]['start_dates'].append(sd)
    
    rows = []
    for prov, s in sorted(provider_summary.items(), key=lambda x: -x[1]['total_fum']):
        if s['total_fum'] == 0 and s['total_members'] == 0:
            continue
        avg_fee = round(statistics.mean(s['fees']), 3) if s['fees'] else None
        avg_ret = round(statistics.mean(s['returns']), 2) if s['returns'] else None
        rows.append([
            prov,
            len(s['fund_names']),
            round(s['total_fum']),
            s['total_members'],
            avg_fee,
            avg_ret,
            f"Latest: {latest}"
        ])
    
    headers = ['Provider', 'Funds', 'Total FUM ($)', 'Total Members', 'Avg Fee %', 'Avg 1yr Return %', 'Data Period']
    save_csv('04-provider-market-overview.csv', headers, rows)
    
    return {'providers': rows, 'latest_period': latest}

# ===== ANALYSIS 5: Asset Allocation Drift =====
def analyze_allocation_drift(data):
    print("\n=== 5. Asset Allocation Drift ===")
    records = data['fma']
    
    drift_data = []
    
    for r in records:
        actual = r.get('asset_allocation_actual', {})
        target = r.get('asset_allocation_target', {})
        
        if not actual or not target:
            continue
        
        total_drift = 0
        categories = ['Cash and cash equivalents', 'New Zealand fixed interest', 
                      'International fixed interest', 'Australasian equities',
                      'International equities', 'Listed Properties',
                      'Unlisted Properties', 'Other', 'Commodities']
        
        for cat in categories:
            a = safe_float(actual.get(cat, 0))
            t = safe_float(target.get(cat, 0))
            if a is not None and t is not None:
                total_drift += abs(a - t)
        
        if total_drift > 0:
            drift_data.append([
                r.get('period_date',''),
                r.get('fund_name',''),
                r.get('provider',''),
                round(total_drift, 2),
                str(actual),
                str(target)
            ])
    
    # Sort by drift (highest first)
    drift_data.sort(key=lambda x: x[3], reverse=True)
    
    headers = ['Period', 'Fund Name', 'Provider', 'Total Drift %', 'Actual', 'Target']
    save_csv('05-allocation-drift.csv', headers, drift_data[:500])
    
    # Summary by period
    period_drift = defaultdict(list)
    for d in drift_data:
        period_drift[d[0]].append(d[3])
    
    rows = []
    for p in sorted(period_drift.keys()):
        vals = period_drift[p]
        rows.append([p, len(vals), round(statistics.mean(vals), 2), round(max(vals), 2)])
    
    save_csv('05-drift-by-period.csv', ['Period', 'Funds', 'Avg Drift %', 'Max Drift %'], rows)
    
    return {'top_drift': drift_data[:10]}

# ===== ANALYSIS 6: Market Cycle Performance =====
def analyze_market_cycles(data):
    print("\n=== 6. Market Cycle Performance ===")
    records = data['fma']
    
    # Define market periods
    cycles = {
        '2020_Q1_CRASH': ('2020-03-31', 'COVID crash'),
        '2020_Q2_RECOVERY': ('2020-06-30', 'Initial recovery'),
        '2021_BOOM': ('2021-09-30', '2021 growth'),
        '2022_DOWNTURN': ('2022-12-31', '2022 downturn'),
    }
    
    # Get return data for each period by fund type (using risk_indicator)
    results = []
    for period_label, (period_date, desc) in cycles.items():
        period_records = [r for r in records if r.get('period_date') == period_date]
        
        # By risk indicator
        risk_groups = defaultdict(list)
        for r in period_records:
            ret1 = safe_float(r.get('1yr_return'))
            risk = safe_int(r.get('risk_indicator'))
            if ret1 is not None and risk:
                risk_groups[risk].append(ret1)
        
        for risk in sorted(risk_groups.keys()):
            vals = risk_groups[risk]
            results.append([
                period_date, desc, risk, len(vals),
                round(statistics.mean(vals), 2),
                round(min(vals), 2),
                round(max(vals), 2)
            ])
        
        # Also by fund name keyword matching as fallback
        type_keywords = {
            'Conservative': ['conservative', 'defensive', 'cash'],
            'Balanced': ['balanced', 'moderate'],
            'Growth': ['growth'],
            'Aggressive': ['aggressive', 'high growth']
        }
        for label, keywords in type_keywords.items():
            fund_returns = []
            for r in period_records:
                name = r.get('fund_name', '').lower()
                if any(k in name for k in keywords):
                    ret1 = safe_float(r.get('1yr_return'))
                    if ret1 is not None:
                        fund_returns.append(ret1)
            if fund_returns:
                results.append([
                    period_date, f"{desc} ({label})", 'N/A', len(fund_returns),
                    round(statistics.mean(fund_returns), 2),
                    round(min(fund_returns), 2),
                    round(max(fund_returns), 2)
                ])
    
    headers = ['Period', 'Description', 'Risk Indicator', 'Funds', 'Avg Return %', 'Min %', 'Max %']
    save_csv('06-market-cycles.csv', headers, results)
    
    return {'cycles': results}

# ===== ANALYSIS 7: Top Holdings Concentration =====
def analyze_holdings_concentration(data):
    print("\n=== 7. Holdings Concentration ===")
    records = data['fma']
    
    # Count how often each holding appears across funds
    holding_counts = Counter()
    type_counts = Counter()
    holding_by_value = defaultdict(float)
    holding_count = 0
    
    for r in records:
        holdings = r.get('top_10_holdings', [])
        if not holdings or not isinstance(holdings, list):
            continue
        for h in holdings:
            name = h.get('name', '')
            pct = safe_float(h.get('percentage', 0))
            htype = h.get('type', '')
            country = h.get('country', '')
            if name:
                clean_name = name.strip()
                holding_counts[clean_name] += 1
                if pct:
                    holding_by_value[clean_name] += pct
                holding_count += 1
                if htype:
                    type_counts[f"{htype} ({country})"] += 1
    
    # Most commonly held investments
    rows = []
    for name, count in holding_counts.most_common(50):
        total_val = round(holding_by_value.get(name, 0), 1)
        rows.append([name, count, round(count / holding_count * 100, 2) if holding_count else 0, total_val])
    
    headers = ['Holding Name', 'Appearances', '% of All Holdings', 'Total Weight %']
    save_csv('07-holdings-concentration.csv', headers, rows)
    
    # By type (cash, equities, fixed interest, etc.)
    type_rows = [[t, c] for t, c in type_counts.most_common()]
    save_csv('07-holdings-by-type.csv', ['Holding Type', 'Count'], type_rows)
    
    return {'top_holdings': rows, 'by_type': type_rows, 'total_appearances': holding_count}

# ===== ANALYSIS 8: Provider Fee Trends Over Time =====
def analyze_fee_trends(data):
    print("\n=== 8. Fee Trends Over Time ===")
    records = data['fma']
    
    # Average fee by period and provider
    period_prov_fees = defaultdict(lambda: defaultdict(list))
    
    for r in records:
        p = r.get('period_date', '')
        prov = r.get('provider', 'Unknown')
        fee = safe_float(r.get('total_fees'))
        if fee is not None:
            period_prov_fees[p][prov].append(fee)
    
    # Major providers only (appear in most periods)
    provider_period_count = Counter()
    for p, provs in period_prov_fees.items():
        for prov in provs:
            provider_period_count[prov] += 1
    
    major_providers = {prov for prov, c in provider_period_count.most_common(20)}
    
    rows = []
    for p in sorted(period_prov_fees.keys()):
        for prov, fees in period_prov_fees[p].items():
            if prov in major_providers:
                rows.append([p, prov, len(fees), round(statistics.mean(fees), 3), round(min(fees), 3), round(max(fees), 3)])
    
    headers = ['Period', 'Provider', 'Funds', 'Avg Fee %', 'Min Fee %', 'Max Fee %']
    save_csv('08-fee-trends-major-providers.csv', headers, rows)
    
    # Overall market average fee per period
    period_avgs = []
    for p in sorted(period_prov_fees.keys()):
        all_fees = []
        for prov, fees in period_prov_fees[p].items():
            all_fees.extend(fees)
        if all_fees:
            period_avgs.append([p, len(all_fees), round(statistics.mean(all_fees), 3), round(statistics.median(all_fees), 3)])
    
    save_csv('08-fee-trends-market.csv', ['Period', 'Funds', 'Avg Fee %', 'Median Fee %'], period_avgs)
    
    return {'by_provider': rows, 'market': period_avgs}

# ===== ANALYSIS 9: Fund Type Return Distribution =====
def analyze_return_distribution(data):
    print("\n=== 9. Return Distribution ===")
    records = data['fma']
    
    # Distribution of 1yr returns by fund type
    period_types = defaultdict(lambda: defaultdict(list))
    
    for r in records:
        p = r.get('period_date', '')
        ret1 = safe_float(r.get('1yr_return'))
        risk = safe_int(r.get('risk_indicator'))
        if ret1 is not None and risk:
            period_types[p][risk].append(ret1)
    
    rows = []
    for p in sorted(period_types.keys()):
        for risk in sorted(period_types[p].keys()):
            vals = period_types[p][risk]
            if len(vals) >= 3:
                sorted_vals = sorted(vals)
                rows.append([
                    p, risk, len(vals),
                    round(statistics.mean(vals), 2),
                    round(statistics.median(vals), 2),
                    round(min(vals), 2),
                    round(max(vals), 2),
                    round(sorted_vals[int(len(vals)*0.25)], 2),
                    round(sorted_vals[int(len(vals)*0.75)], 2)
                ])
    
    headers = ['Period', 'Risk(1-7)', 'Funds', 'Mean %', 'Median %', 'Min %', 'Max %', 'Q1(25th)%', 'Q3(75th)%']
    save_csv('09-return-distribution.csv', headers, rows)
    
    return {'distribution': rows}

# ===== ANALYSIS 10: Fund Age vs Performance =====
def analyze_fund_age_vs_performance(data):
    print("\n=== 10. Fund Age vs Performance ===")
    records = data['fma']
    
    results = []
    for r in records:
        start = r.get('fund_start_date', '')
        ret1 = safe_float(r.get('1yr_return'))
        fee = safe_float(r.get('total_fees'))
        fum = safe_float(r.get('fum'))
        members = safe_int(r.get('members'))
        
        if start and ret1 is not None:
            results.append([
                r.get('period_date', ''),
                r.get('fund_name', ''),
                r.get('provider', ''),
                start,
                ret1,
                fee if fee else None,
                fum if fum else None,
                members if members else None
            ])
    
    headers = ['Period', 'Fund Name', 'Provider', 'Start Date', '1yr Return %', 'Fee %', 'FUM', 'Members']
    save_csv('10-fund-age-vs-performance.csv', headers, results)
    
    return {'count': len(results)}

# ===== RUN ALL =====
def run_all():
    print("KiwiSaver Data Analysis Suite")
    print("=" * 50)
    
    data = load_data()
    
    results = {}
    results['fee_impact'] = analyze_fees_vs_returns(data)
    results['risk_reward'] = analyze_risk_reward(data)
    results['persistence'] = analyze_performance_persistence(data)
    results['providers'] = analyze_providers(data)
    results['allocation_drift'] = analyze_allocation_drift(data)
    results['market_cycles'] = analyze_market_cycles(data)
    results['holdings'] = analyze_holdings_concentration(data)
    results['fee_trends'] = analyze_fee_trends(data)
    results['return_dist'] = analyze_return_distribution(data)
    results['fund_age'] = analyze_fund_age_vs_performance(data)
    
    # Save combined index
    index = {
        'generated': datetime.now().isoformat(),
        'data_sources': {
            'fma_records': len(data['fma']),
            'smart_investor_funds': len(data['smart_investor']),
            'annual_reports': len(data['reports']),
        },
        'analyses': list(results.keys()),
        'output_dir': OUTDIR,
    }
    
    with open(f"{OUTDIR}/analysis-index.json", 'w') as f:
        json.dump(index, f, indent=2)
    
    print(f"\n{'='*50}")
    print(f"All analyses saved to {OUTDIR}/")
    print(f"Add new data and re-run: python3 analysis.py")

if __name__ == '__main__':
    run_all()
