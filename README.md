# HighTechExports

High-tech exports from India: how high-tech goods have evolved as a share of
**manufacturing exports** from FY 2006-07 to FY 2025-26, and how they are spread
across **states and districts** in FY 2025-26.

## Planned approach

1. **Clean the raw DGCI&S data** (HS6-level exports) — *done, see below*.
2. **Manufacturing exports** — follow the World Bank WITS definition
   (SITC Rev.3 sections 5–8, excluding division 68 (non-ferrous metals) and
   group 667 (pearls/precious stones)). This needs an HS6 → SITC concordance.
3. **High-tech exports** — the World Bank / Eurostat high-technology product
   list (SITC-based), again mapped onto HS6.
4. **Indicators** — high-tech share of manufacturing exports, nationally by year
   (FY07–FY26) and by state/district for FY 2025-26.
5. **Outputs** — time-series plots, state and district choropleths.

## Repository layout

```
data/
  raw/
    yearly_hs6/          DGCI&S yearly HS6 export time series (as downloaded)
    district_2025_26/    DGCI&S "state of origin" State x District x HS6 (zip of 29 .xls)
  processed/             cleaned outputs (produced by scripts/)
scripts/
  01_clean_export_data.py
requirements.txt
```

Reproduce: `pip install -r requirements.txt && python scripts/01_clean_export_data.py`

## Data sources

All data are from DGCI&S (Directorate General of Commercial Intelligence and
Statistics, Ministry of Commerce), exports **including re-exports**.

| Raw file | Content | Units |
|---|---|---|
| `dgcis_yearly_hs6_2006-07_to_2015-16.xls` | Yearly time series, 6-digit HS, FY 2006-07 – 2015-16 | US$ |
| `dgcis_yearly_hs6_2016-17_to_2025-26.xls` | Yearly time series, 6-digit HS, FY 2016-17 – 2025-26 | US$ |
| `dgcis_state_district_hs6_2025-26.zip` | State of origin × District × HS6, Apr-2025 – Mar-2026 (plus March 2026 alone) | INR and US$ |

The yearly downloads contain **US$ only** (no INR). Indian financial years run
April–March; `FY 2025-26` = Apr 2025 – Mar 2026 (`fy_end_year = 2026`).

## Processed data (`data/processed/`)

| File | Grain | Key columns |
|---|---|---|
| `india_exports_hs6_fy2007_2026_long.csv` | HS6 × FY (non-zero rows only, ~99k rows) | `hs6, hs4, hs2, description, fy, fy_end_year, export_usd, export_usd_mn` |
| `india_exports_hs6_fy2007_2026_wide.csv` | HS6 × 20 FY columns, **US$ million**, zeros filled | `hs6, description, FY2006-07 … FY2025-26` |
| `hs6_descriptions.csv` | every (HS6, description) variant DGCI&S used, with first/last FY of trade | for checking HS revisions |
| `india_exports_national_totals.csv` | FY | `n_hs6, export_usd_bn` |
| `district_exports_hs6_fy2025_26.parquet` | State × District × HS6, FY 2025-26 (280,165 rows) | `state, district, hs6, hs4, hs2, description, export_usd, export_usd_mn, export_inr, mar2026_usd, mar2026_inr` |
| `district_exports_state_totals_fy2025_26.csv` | State | `n_districts, n_hs6, export_usd_mn, export_inr_cr` |

Conventions: `hs6` is always a 6-character string with leading zeros (`"010121"`);
`export_usd` is raw US$, `export_usd_mn` is US$ million. The district file is
Parquet (6 MB, keeps dtypes; a CSV would be ~40 MB). Read it with
`pd.read_parquet(...)`.

### Cleaning notes

- **Merging the two yearly files.** They cover disjoint years, so they are
  stacked. The same HS6 code often appears on several rows with different
  descriptions (wording changes / HS 2007, 2012, 2017, 2022 revisions). It was
  verified that no two description-variants of a code carry trade in the same
  year, so values are summed by `(hs6, fy)` without double counting. The most
  recently used description is kept as the label; all variants are in
  `hs6_descriptions.csv`.
- **HS nomenclature changes over time.** HS6 codes are as reported in each year
  (India's ITC-HS follows HS 2007 → 2012 → 2017 → 2022). Codes that were split
  or merged across revisions will need to be handled when mapping to SITC —
  probably by using the HS-vintage-specific WITS concordances per year.
- Descriptions had runs of spaces collapsed; state/district names upper-cased
  and trimmed. No duplicate State × District × HS6 rows were found.
- `999300` (special transactions) and `999999` (unspecified) are retained;
  they are large in some years (e.g. ~US$11 bn "unspecified" in FY 2010-11 and
  2011-12) and will fall outside manufacturing.

### Sanity checks

National totals (US$ bn) from the cleaned yearly series:

| FY | 06-07 | 10-11 | 15-16 | 20-21 | 21-22 | 22-23 | 23-24 | 24-25 | 25-26 |
|---|---|---|---|---|---|---|---|---|---|
| Exports | 126.4 | 249.8 | 262.3 | 291.8 | 422.0 | 451.1 | 437.1 | 437.7 | 441.5 |

- The district file sums to **US$ 441.45 bn**, exactly matching the national
  FY 2025-26 total from the yearly series.
- The district file has 37 states/UTs and 705 districts. It includes an
  **`UNSPECIFIED` state (US$ 4.33 bn)**, almost all of it petroleum products
  (HS 271019, 271600 = electrical energy). This should not affect high-tech
  shares, but must be kept in mind when computing state shares of the national
  total.
- "DADRA,NH,DAMAN,DIU" is reported as one UT (merged in 2020) — the map
  boundaries will need to match.

Top states, FY 2025-26 (US$ bn): Gujarat 110.6, Maharashtra 69.9,
Tamil Nadu 59.3, Karnataka 34.4, Uttar Pradesh 22.8, Haryana 20.6.
