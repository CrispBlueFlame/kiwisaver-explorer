# KiwiSaver: what the data actually shows

Every figure below is produced by a short script from the same public data the
site uses. To reproduce all of them yourself:

```bash
python3 scripts/findings.py
```

The script reads only `data/current-funds.json` (418 current funds) and
`data/fma-history.json` (the FMA quarterly history, 2013 to 2022). It needs
nothing beyond the Python standard library. Every claim here maps to a block of
that output, so you can check the numbers without reading the site's JavaScript.

A note on honesty: one of the working headlines going in was "performance is
near random." The data does not support that as stated, so it is not claimed
here. What the data does support is set out below, caveats included.

---

## Finding 1: Fees vary about 8x, and index funds cost roughly 3x less than the median

- **Claim:** the fee a KiwiSaver member pays depends far more on which fund they
  happen to be in than on anything they receive for it.
- **Method:** take the stated annual fee for all 418 current funds; report the
  range, the median, and where the low-cost index providers sit.
- **Figures:** fees run from about 0.25% to 2.11% (roughly an 8x spread). The
  median fund charges 0.85%. Simplicity's index funds charge a flat 0.25%,
  about 3.4x cheaper than the median fund and about 4.4x cheaper than the median
  Growth fund (1.10%).
- **Caveat:** fees are provider-reported to the FMA and defined consistently
  across the dataset, but funds bundle slightly different services, so this is a
  headline cost comparison, not a like-for-like invoice.

## Finding 2: Paying more does not buy more

- **Claim:** across the market, a higher fee does not come with a higher net
  return.
- **Method:** correlate each fund's fee with its 5-year net return (n = 290
  funds that report both). Then repeat inside each risk category, since riskier
  funds earn more on average and would otherwise mask the relationship.
- **Figures:** overall correlation is +0.02, effectively zero. Inside the
  higher-risk categories it turns negative (Growth -0.26, Aggressive -0.30),
  meaning the pricier funds in those groups tended to deliver slightly less, not
  more.
- **Caveat:** returns are after fees and provider-reported. This is an
  association across funds, not a controlled experiment; it says the premium you
  pay is not showing up as extra return, not that fees actively cause losses.

## Finding 3: Past performance is a weak, inconsistent guide

- **Claim:** a fund's recent ranking is not a reliable way to pick the next
  period's winner.
- **Method:** for the 132 funds with data in both windows, rank funds by average
  return in 2016 to 2018 and again in 2020 to 2022, and measure how much the
  ranking holds. Do it first raw, then within each risk category (the honest
  test, since otherwise you are just measuring that Aggressive beats
  Conservative in both windows).
- **Figures:** raw persistence looks strong (rank correlation +0.87) but that is
  the risk level repeating. Within a category it drops to modest and uneven:
  Balanced +0.72, Growth +0.62, Conservative +0.54, Aggressive only +0.17.
- **Reading:** some funds do persist a little within their category, but
  inconsistently, and (from Finding 2) the fee you pay does not tell you which.
  Cost is the one lever a member can see and control up front.

## Finding 4: Same label, same portfolio

- **Claim:** funds sharing a risk label hold near-identical asset mixes, so much
  of the fee gap buys near-identical exposure.
- **Method:** for each fund's latest reported quarter, sum the growth assets
  (Australasian equities, international equities, listed and unlisted property)
  and measure the spread within each category.
- **Figures:** the growth-asset share barely moves within a category. Balanced
  funds average 50% growth assets with a standard deviation of about 8 points
  (middle half 46% to 57%); Growth funds average 74% (std-dev about 8 points).
  Defensive funds sit at essentially 0% growth assets across the board.
- **Caveat:** this is high-level asset allocation, not individual security
  holdings, which the FMA data does not break out. It shows funds of a given
  label take very similar market exposure, not that they hold the identical
  shares.

## Finding 5: What the fee gap costs in dollars

- **Claim:** small fee differences compound into life-changing sums over a
  KiwiSaver lifetime.
- **Method:** project a balance forward giving every fund the same 5% gross
  return and changing only the fee, so the gap shown is pure fee drag.
- **Figures:**
  - A $50,000 balance left for 30 years grows to about $207,000 at 0.25%, but
    only about $173,000 at the 0.85% median fee (about $34,000 less) and about
    $161,000 at the 1.10% median Growth fee (about $47,000 less).
  - $433 a month (about $100 a week) for 40 years grows to about $619,000 at
    0.25%, versus about $531,000 at 0.85% (about $88,000 less) and about
    $499,000 at 1.10% (about $120,000 less).
- **Caveat:** 5% gross is an illustrative assumption applied equally to every
  fund; it is not a forecast. The point is the size of the fee gap, which holds
  at any reasonable return assumption.

---

## Sources and reproducibility

- Current snapshot: Smart Investor (Sorted) plus a FundCompare snapshot.
- History: FMA Quarterly Fund Updates, 2013 to 2022, with 2013 to 2015 recovered
  from Wayback Machine archives. Pre-2013 context comes from Wayback-recovered
  Morningstar KiwiSaver Survey category averages.
- Full provenance, including how each source was collected and the data traps
  handled along the way, is in `DATA_SOURCES.md`.
- Data is CC BY 4.0. This is educational analysis, not financial advice. Fees
  and returns are provider-reported to the FMA and not independently audited.

Repository: https://github.com/CrispBlueFlame/kiwisaver-explorer
