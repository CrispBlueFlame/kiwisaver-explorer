#!/usr/bin/env python3
"""
Smart Investor KiwiSaver Fund Scraper

Fetches ALL pages of the Smart Investor KiwiSaver funds API,
parses HTML fragments to extract structured fund data, and saves as JSON.

Usage: source .venv/bin/activate && python3 scrape_smart_investor.py
"""

import json
import re
import time
import os
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    print("Error: requests library not found. Run: uv pip install requests")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 not found. Run: uv pip install beautifulsoup4")
    sys.exit(1)

# ─── Configuration ────────────────────────────────────────────────────────────

BASE_URL = (
    "https://www.smartinvestor.sorted.org.nz/kiwisaver-and-managed-funds/"
    "get_results/?managedFundTypes=kiwisaver-funds&fundTypes=all"
    "&searchType=quick&sort=name-asc&page={PAGE}"
)

HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.smartinvestor.sorted.org.nz/kiwisaver-and-managed-funds/",
    "Accept": "text/html, */*; q=0.01",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
}

RATE_LIMIT_SECONDS = 2  # Between requests
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extracted")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "smart_investor_raw.json")

# ─── Parsing Functions ────────────────────────────────────────────────────────


def clean_pct(text):
    """Extract a float percentage from text like '3.44%' or '1.23<sup> %</sup>'."""
    if not text:
        return None
    # Remove HTML tags, whitespace
    text = re.sub(r'<[^>]+>', '', text)
    text = text.strip()
    # Match pattern like "3.44" or "-10.95"
    m = re.search(r'(-?\d+\.?\d*)', text)
    if m:
        val = float(m.group(1))
        # Flag anomalous returns
        if abs(val) > 40:
            print(f"  ⚠ ANOMALOUS VALUE: {val}% from '{text}'")
        return val
    return None


def parse_provider_name(card):
    """Extract provider name from the card header."""
    el = card.find('p', class_='colour--grey-mid')
    if el:
        return el.get_text(strip=True)
    # Fallback: data-scheme attribute
    return card.get('data-scheme', '').strip()


def parse_fund_name(card):
    """Extract fund name from the card title (strip SVG icons)."""
    el = card.find('h3', class_='card__title')
    if not el:
        return ''
    # Clone to avoid modifying original
    import copy
    clone = copy.copy(el)
    # Remove all SVG elements
    for svg in clone.find_all('svg'):
        svg.decompose()
    return clone.get_text(strip=True)


def parse_fund_type(card):
    """Extract fund type from tags (e.g., 'Conservative', 'Growth')."""
    tags = card.find_all('div', class_='tag')
    fund_types = []
    for tag in tags:
        t = tag.get_text(strip=True).replace('Tag -', '').strip()
        if t != 'KiwiSaver':
            fund_types.append(t)
    return fund_types


def parse_fee_pct(card):
    """
    Extract annual fee % from card__column--second.
    The fee is shown in a <span class="colour--purple-dark"> inside a doughnut chart.
    """
    col = card.find('div', class_='card__column--second')
    if not col:
        return None
    # The fee % is in <span class="colour--purple-dark"> or <b> inside it
    fee_el = col.find('span', class_='colour--purple-dark')
    if fee_el:
        return clean_pct(fee_el.get_text())
    # Try <b> inside the legend
    b_el = col.find('b', class_='colour--purple-dark')
    if b_el:
        return clean_pct(b_el.get_text())
    return None


def parse_5yr_return(card):
    """
    Extract 5-year return % from card__column--third.
    Shown in a <span class="colour--green-mid"> or <b class="colour--green-mid">.
    """
    col = card.find('div', class_='card__column--third')
    if not col:
        return None
    # Check for "No five-year data available" first
    no_data = col.find(string=re.compile(r'No.*five.*year.*data', re.IGNORECASE))
    if no_data:
        return None
    # Try the main return value
    ret_el = col.find('span', class_='colour--green-mid')
    if ret_el:
        return clean_pct(ret_el.get_text())
    b_el = col.find('b', class_='colour--green-mid')
    if b_el:
        return clean_pct(b_el.get_text())
    # Also try h1 with colour--green-mid
    h1_el = col.find('h1', class_='colour--green-mid')
    if h1_el:
        return clean_pct(h1_el.get_text())
    return None


def parse_yearly_returns(card):
    """
    Extract yearly returns from the returns tab panel (card__column--ninth).
    Returns a dict like {'2026': 22.03, '2025': -10.95, ...}
    """
    # Find the returns tab - it has data-id="returns" and class card__tab
    returns_tab = card.find('div', {'data-id': 'returns'})
    if not returns_tab:
        return {}
    
    yearly = {}
    
    # Method 1: Parse the legend structure
    # Find the header row to get years
    header_row = returns_tab.find('div', class_='line-chart__legend__row--header')
    if not header_row:
        # Try finding the legend by its structure
        legend_rows = returns_tab.find_all('div', class_='line-chart__legend__row')
        header_row = legend_rows[0] if legend_rows else None
    
    years = []
    if header_row:
        alt_row = header_row.find('div', class_='line-chart__legend__row-alt')
        if alt_row:
            year_divs = alt_row.find_all('div', class_='line-chart__legend__column-alt')
            years = [y.get_text(strip=True) for y in year_divs]
    
    # Find the "This fund" row for values
    fund_row = None
    legend_rows = returns_tab.find_all('div', class_='line-chart__legend__row')
    for row in legend_rows:
        # Check if this is the "This fund" row
        label_el = row.find('div', class_='line-chart__legend__column')
        if label_el and 'this fund' in label_el.get_text(strip=True).lower():
            fund_row = row
            break
    
    if fund_row and years:
        alt_row = fund_row.find('div', class_='line-chart__legend__row-alt')
        if alt_row:
            value_divs = alt_row.find_all('div', class_='line-chart__legend__column-alt')
            for i, val_div in enumerate(value_divs):
                if i < len(years):
                    # Value may be in <b> tag or directly in the div
                    b = val_div.find('b')
                    if b:
                        raw = b.get_text()
                    else:
                        raw = val_div.get_text()
                    val = clean_pct(raw)
                    if val is not None:
                        yearly[years[i]] = val
    
    # Method 2: Fallback to canvas data-dataset attribute
    if not yearly:
        canvas = returns_tab.find('canvas', class_='js-inline-line-chart')
        if canvas:
            dataset_str = canvas.get('data-dataset', '[]')
            try:
                dataset = json.loads(dataset_str)
                for entry in dataset:
                    if 'year' in entry and 'fund' in entry:
                        fund_val = entry.get('fund')
                        if fund_val is not None:
                            try:
                                yearly[str(entry['year'])] = float(fund_val)
                            except (ValueError, TypeError):
                                pass
            except (json.JSONDecodeError, TypeError):
                pass
    
    return yearly


def parse_1yr_return(yearly_returns):
    """Get the most recent year's return from yearly data."""
    if not yearly_returns:
        return None
    # Find the latest year
    try:
        latest_year = max(yearly_returns.keys(), key=lambda y: int(y) if y.isdigit() else 0)
        return yearly_returns[latest_year]
    except (ValueError, StopIteration):
        return None


def parse_3yr_return(yearly_returns):
    """Calculate approximate 3-year return from yearly data if available."""
    # Not directly available from API - needs 3 years of data to average
    return None


def parse_10yr_return(yearly_returns):
    """10-year return - not available from API (only 5 years shown)."""
    return None


def parse_fund_size(card):
    """Fund size/FUM - not available in the API card HTML."""
    return None


def parse_risk_indicator(card):
    """Risk indicator - not available in the API card HTML."""
    return None


def parse_card(card_html):
    """Parse a single fund card HTML and return structured data."""
    soup = BeautifulSoup(card_html, 'html.parser')
    card = soup.find('div', class_='card')
    if not card:
        return None
    
    provider_name = parse_provider_name(card)
    fund_name = parse_fund_name(card)
    fund_types = parse_fund_type(card)
    annual_fee_pct = parse_fee_pct(card)
    ret_5yr = parse_5yr_return(card)
    yearly_returns = parse_yearly_returns(card)
    ret_1yr = parse_1yr_return(yearly_returns)
    
    fund_record = {
        "provider_name": provider_name,
        "fund_name": fund_name,
        "fund_type": fund_types,
        "1yr_return": ret_1yr,
        "3yr_return": None,
        "5yr_return": ret_5yr,
        "10yr_return": None,
        "annual_fee_pct": annual_fee_pct,
        "fund_size_fum": None,
        "risk_indicator": None,
        "yearly_returns": yearly_returns,
        "raw_data_scheme": card.get('data-scheme', ''),
    }
    
    # Flag anomalous returns
    for period, val in [('1yr', ret_1yr), ('5yr', ret_5yr)]:
        if val is not None and abs(val) > 40:
            print(f"  ⚠ Anomalous {period} return for {provider_name} - {fund_name}: {val}%")
    
    return fund_record


# ─── Fetching ─────────────────────────────────────────────────────────────────


def fetch_page(page_num, session):
    """Fetch a single API page and return the JSON response."""
    url = BASE_URL.format(PAGE=page_num)
    print(f"  Fetching page {page_num}...", end=' ', flush=True)
    
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print(f"✓ ({len(data.get('results', []))} results)")
        return data
    except requests.RequestException as e:
        print(f"✗ ERROR: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"✗ JSON parse error: {e}")
        return None


def scrape_all_pages():
    """Scrape all pages of the API."""
    session = requests.Session()
    
    print("=" * 60)
    print("Smart Investor KiwiSaver Fund Scraper")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # First, try to get the count from the local cached first page
    total_funds = 419  # Known from context
    results_per_page = 10
    total_pages = (total_funds + results_per_page - 1) // results_per_page
    
    print(f"\nTotal funds: {total_funds}, Pages to fetch: {total_pages}")
    print(f"Rate limit: {RATE_LIMIT_SECONDS}s between requests")
    
    all_funds = []
    failed_pages = []
    anomalous_funds = []
    
    for page in range(1, total_pages + 1):
        data = fetch_page(page, session)
        
        if data is None:
            failed_pages.append(page)
            # Wait and retry once
            time.sleep(RATE_LIMIT_SECONDS * 2)
            print(f"  Retrying page {page}...")
            data = fetch_page(page, session)
            if data is None:
                failed_pages.append(page)
                continue
        
        results_html = data.get('results', [])
        
        for idx, card_html in enumerate(results_html):
            fund = parse_card(card_html)
            if fund:
                all_funds.append(fund)
        
        # Progress
        print(f"  → {len(all_funds)}/{total_funds} funds extracted so far")
        
        # Rate limit
        time.sleep(RATE_LIMIT_SECONDS)
    
    print(f"\n{'='*60}")
    print(f"Scraping complete: {len(all_funds)} funds extracted")
    if failed_pages:
        print(f"Failed pages: {failed_pages}")
    print(f"{'='*60}")
    
    return all_funds


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    all_funds = scrape_all_pages()
    
    # Save results
    output = {
        "metadata": {
            "source": "Smart Investor (Sorted NZ)",
            "url": "https://www.smartinvestor.sorted.org.nz/kiwisaver-and-managed-funds/",
            "scraped_at": datetime.now().isoformat(),
            "total_funds": len(all_funds),
            "fields_extracted": [
                "provider_name", "fund_name", "fund_type",
                "1yr_return", "3yr_return", "5yr_return", "10yr_return",
                "annual_fee_pct", "fund_size_fum", "risk_indicator",
                "yearly_returns"
            ]
        },
        "funds": all_funds
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Data saved to: {OUTPUT_FILE}")
    print(f"   File size: {os.path.getsize(OUTPUT_FILE):,} bytes")
    
    # Summary stats
    with_fees = sum(1 for f in all_funds if f['annual_fee_pct'] is not None)
    with_5yr = sum(1 for f in all_funds if f['5yr_return'] is not None)
    with_1yr = sum(1 for f in all_funds if f['1yr_return'] is not None)
    
    print(f"\n📊 Summary:")
    print(f"   Funds with fee data: {with_fees}/{len(all_funds)}")
    print(f"   Funds with 5yr return: {with_5yr}/{len(all_funds)}")
    print(f"   Funds with 1yr return: {with_1yr}/{len(all_funds)}")
    
    # Breakdown by fund type
    type_counts = {}
    for f in all_funds:
        for ft in f['fund_type']:
            type_counts[ft] = type_counts.get(ft, 0) + 1
    if type_counts:
        print(f"\n📊 Fund type breakdown:")
        for ft, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"   {ft}: {count}")


if __name__ == '__main__':
    main()
