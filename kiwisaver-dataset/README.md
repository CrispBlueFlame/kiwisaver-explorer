# NZ KiwiSaver Dataset

Historical KiwiSaver fund performance data, fees, asset allocations, and holdings, collected from public sources. Free for anyone to use.

## The Problem

Until December 2022, the Financial Markets Authority published consolidated quarterly KiwiSaver fund data as CSV files on their website. In 2023 they stopped. The data still exists on the Companies Office Disclose Register, but accessing it in bulk now requires applying for a business API key. This dataset preserves the historical record and provides tools to keep it current.

## Dataset Summary

| Source | Period | Records | Type |
|--------|--------|---------|------|
| FMA Quarterly Fund Updates | Sep 2013 - Dec 2022 | 9,755 | Fund-level returns, fees, allocations, holdings. 2013-2015 recovered from Wayback-archived XLSB files no longer on the FMA site; overlapping 2015 quarters deduplicated. |
| Smart Investor (Sorted) | Current snapshot | 419 | Fund names, types, fees, 1yr/5yr returns |
| FundCompare | Current snapshot | 26 providers | Provider-level AUM, members, fees |
| Provider Fund Update PDFs | 2023-2026 | 499 | Fund-level returns, fees, FUM from ANZ, BNZ, Milford, Fisher, Mercer, Simplicity, Booster |
| FMA Annual Reports | 2011-2025 | 15 | Industry aggregates, member counts, FUM |
| FSC Quarterly Spotlights | Dec 2020 - Mar 2026 | 10 | Provider-level FUM and member estimates |
| Morningstar KiwiSaver 360 Surveys | Sep 2023 - Dec 2025 | 11 | Fund performance tables and market commentary |
| IRD Statistics | Jun 2012 - Jun 2025 | 1 | Member demographics, contributions, withdrawals |

## Data Dictionary

### data/fma-quarterly/combined.csv

| Column | Description |
|--------|-------------|
| quarter | Reporting period end date (YYYY-MM-DD) |
| fund_number | Unique fund identifier |
| fund_name | Name of the fund |
| scheme_name | Name of the KiwiSaver scheme |
| provider | Provider/manager name |
| fum | Fund value in NZD |
| members | Number of members in the fund |
| fund_start_date | Date the fund launched |
| return_1yr | Past year return after fees and tax (%) |
| return_yr1 through return_yr10 | Individual annual returns going back 10 years |
| fee_total | Total annual fund fees (%) |
| risk_indicator | Risk indicator (1-7, 1=lowest risk) |
| return_5yr_avg | Average 5-year return (%) |
| alloc_cash | Actual allocation to cash (%) |
| alloc_nz_fixed | Actual allocation to NZ fixed interest (%) |
| alloc_intl_fixed | Actual allocation to international fixed interest (%) |
| alloc_aus_equities | Actual allocation to Australasian equities (%) |
| alloc_intl_equities | Actual allocation to international equities (%) |
| alloc_listed_property | Actual allocation to listed property (%) |
| alloc_unlisted_property | Actual allocation to unlisted property (%) |
| alloc_other | Actual allocation to other assets (%) |
| alloc_commodities | Actual allocation to commodities (%) |
| target_* | Target allocation for each asset class (same categories) |

## Known Data Gaps

### Missing quarterly periods
- 2013 Q1, Q2 (recovered archives start Sep 2013)
- 2017 Q1, Q2, Q3
- 2019 Q3
- 2021 Q2
- 2022 Q2, Q3

### Post-2022
No consolidated quarterly fund data after December 2022. The FMA stopped publishing. Data for 2023-2026 exists on the Disclose Register but requires API access.

### Pre-2013
KiwiSaver launched in 2007. Fund-level quarterly data starts September 2013 (the earliest Wayback-recovered FMA archive). For earlier years, the FMA annual reports provide industry-level aggregates, and Wayback-recovered Morningstar category averages give market context back to 2010.

## License

CC BY 4.0. Free to share and adapt with attribution.

## Analysis

Re-run with: scripts/analysis.py

See analysis/ directory for pre-computed outputs.
