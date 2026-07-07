# How We Got This Data, and Why It Should Be Easier

This document explains where every piece of KiwiSaver data in this dataset came from, how we got it, and what it would take for an average person to do the same thing.

## The Short Version

KiwiSaver holds roughly $123 billion for about 3.4 million New Zealanders (approximate industry totals from FMA and RBNZ reporting, 2025; these are context figures, not outputs of this dataset). The fund-level data that shows how that money is being managed is scattered across multiple government websites, provider portals, and archived files. None of it is available in one place. None of it is easy to find. Most of it requires programming skills, historical knowledge of where files used to live, or an application for a business API key.

We spent roughly 8 hours collecting data that should be downloadable from a single government webpage.

This document describes the full data-collection effort behind the dataset. The KiwiSaver Explorer tool built on top of it draws mainly on two of these sources: the FMA quarterly history (September 2015 to December 2022) and the current Smart Investor snapshot.

## What We Collected and Where It Came From

### 1. FMA Quarterly Fund Updates (2015-2022)

**Source:** Financial Markets Authority website at fma.govt.nz

From 2015 to December 2022, the FMA published consolidated spreadsheets every quarter containing every KiwiSaver fund's returns, fees, asset allocations, and top 10 holdings. These were CSV files: simple, machine-readable, usable in Excel.

We found the URLs by knowing they existed. The FMA's managed fund data page still lists them, but only for 2018 onwards. For older files (2015-2017), we had to guess the URL pattern. Some of the 2015-2016 files were only available as old binary Excel formats (.xls, .xlsb) that required special software to open.

**Difficulty for an average person:** High. Finding the page is easy, but the files stop at December 2022. Earlier files use different naming conventions. Some are in formats Excel struggles with.

### 2. Wayback Machine Archives (2013-2015)

**Source:** Internet Archive at archive.org

Before 2015, the FMA published KiwiSaver data in a different format using SAS-generated XLSB files. These files don't exist on the FMA's current website anymore. They were only preserved because the Internet Archive's Wayback Machine happened to crawl them.

We queried the Wayback Machine's CDX API to find all files that ever existed at the FMA's spreadsheets URL. This returned 12 XLSB files from September 2013 through December 2015 that aren't linked anywhere on the live FMA site.

**Difficulty for an average person:** Very high. You'd need to know the Wayback Machine exists, how to query its API, and how to download files from it. The files use cryptic column names with no documentation.

### 3. Smart Investor (Sorted)

**Source:** Sorted's Smart Investor tool at smartinvestor.sorted.org.nz

The Retirement Commission runs a fund comparison website listing 419 KiwiSaver funds. You can browse it in a browser, but the data loads from a backend API. We found the API by watching network requests in browser developer tools, then scraped 42 pages to extract the data.

**Difficulty for an average person:** Medium-high. Browsing the website is easy. Getting the raw data requires developer tools and coding.

### 4. FundCompare

**Source:** FundCompare.co.nz

A private comparison site with a public JSON API at predictable URLs. No authentication needed.

**Difficulty for an average person:** Medium if you know about the API. Unlikely an average person would find it.

### 5. Provider Fund Update PDFs (2023-2026)

**Source:** Individual KiwiSaver provider websites

After the FMA stopped publishing consolidated data in December 2022, the only way to get fund-level data for recent years is to visit each provider's website and download their individual quarterly fund update PDFs. Every provider is legally required to publish these, but there's no central directory of where they are.

We wrote separate scrapers for 7 providers: ANZ (196 PDFs), BNZ (64), Milford (78), Fisher Funds (82), Mercer (56), Simplicity (23), Booster (1), roughly 500 PDF files in all, which yielded 499 usable fund-update records in the dataset. Three major providers (ASB, Westpac, Generate) blocked our attempts or didn't host PDFs directly.

**Difficulty for an average person:** Extremely high. No central list exists. Each provider uses a different website and naming system. You'd need to find, download, and manually transcribe roughly 500 PDFs one by one.

### 6. FMA Annual Reports (2011-2025)

**Source:** Financial Markets Authority website

15 annual reports with industry-level data. Direct downloads from fma.govt.nz. The 15 PDFs use 5 different filename conventions across different years.

**Difficulty for an average person:** Low to medium. The reports are all on the FMA's website but use inconsistent filenames.

### 7. IRD Statistics

**Source:** Inland Revenue at ird.govt.nz

Annual and monthly KiwiSaver statistics covering membership, contributions, withdrawals, and demographics. Direct download of Excel files.

**Difficulty for an average person:** Low. This is the easiest source to access.

### 8. Morningstar KiwiSaver 360 Surveys

**Source:** Morningstar Australia and Milford Asset Management

11 quarterly survey PDFs with fund performance tables and market commentary.

**Difficulty for an average person:** Low-medium. Publicly available but requires knowing where to look.

### 9. FSC Quarterly Spotlights

**Source:** Financial Services Council

10 quarterly spotlight PDFs with industry-level FUM and member counts.

**Difficulty for an average person:** Low.

### 10. RBNZ Assets by Sector

**Source:** Reserve Bank of New Zealand

Quarterly aggregate KiwiSaver assets by asset class. Data table visible on their website. Download blocked by Cloudflare.

**Difficulty for an average person:** Low if browsing. High if you want the downloadable file.

## What We Could Not Get

### Disclose Register API

The Companies Office runs the Disclose Register, the legal repository where every KiwiSaver provider submits their quarterly fund data. This is the authoritative source.

We could not access it because it requires creating an account, subscribing to the API, and waiting for approval. This is the only way to get post-2022 data for all providers in a structured format.

## What This Means for the Average Kiwi

If you wanted to do what we did, here's what you'd need:

**Skills:** Command line, Python, APIs, regex, PDF parsing, Wayback Machine usage. 8+ hours for someone with these skills. Days or weeks without them.

**Software:** Python 3, multiple libraries, code editor, command line tools.

**Knowledge:** You'd need to know the FMA used to publish CSVs but stopped, the Wayback Machine archived old files, FundCompare has a hidden API, Smart Investor loads data through an inspectable API, each provider publishes PDFs on their own website, IRD has downloadable statistics, and several other niche facts.

**The frustrating part:** Every piece of this data is publicly available. None of it is secret. But it's scattered across 10+ different websites, each with its own format and access method. The FMA proved it can be done centrally when they published consolidated CSVs from 2015 to 2022. They stopped, and now the data effectively doesn't exist for anyone who doesn't have the technical skills and patience of a software engineer.
