# KiwiSaver Explorer

Interactive, static site for finding and comparing New Zealand KiwiSaver funds.
Three modes:

- **Find my fund** — answer a few questions (risk, horizon, balance, fee/return priorities, ethical preference) and get ranked, explained recommendations.
- **Data explorer** — filter, sort, search and export every fund; click a fund for its history (returns, fees, allocation) from the FMA quarterly data.
- **Chart builder** — build scatter, bar, distribution and historical line charts across any dimension.

No backend, no build step. Data is baked in as JSON and everything runs client-side.

## Run locally

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

Must be served over HTTP (the app fetches JSON), not opened as a `file://` URL.

## Rebuild the data

Source data lives in `../kiwisaver-dataset`. To regenerate the JSON payloads:

```bash
python3 scripts/build-data.py
```

## Deploy to GitHub Pages

Push to GitHub, then in **Settings → Pages** set the source to the `main` branch, root folder. The site is served as-is.

## Key findings

Three things the data shows, each reproducible from the published JSON by running
`python3 scripts/findings.py`:

1. Fees vary about 8x across funds, and index funds cost roughly 3x less than the median.
2. Paying a higher fee does not buy a higher net return (correlation is effectively zero, and negative in the higher-risk categories).
3. Funds sharing a risk label hold near-identical asset mixes, so much of the fee gap buys near-identical exposure.

Full write-up, methods, figures and caveats are in [`FINDINGS.md`](FINDINGS.md).

## Data & disclaimer

Data compiled from public sources (Smart Investor / Sorted, FundCompare, FMA quarterly fund updates 2015–2022) under CC BY 4.0. This is an educational tool, **not financial advice**. Always check a fund's current Product Disclosure Statement.
