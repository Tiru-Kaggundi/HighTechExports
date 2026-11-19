"""
Step 01 - Clean raw DGCI&S export data.

Inputs (data/raw/):
  yearly_hs6/dgcis_yearly_hs6_2006-07_to_2015-16.xls
  yearly_hs6/dgcis_yearly_hs6_2016-17_to_2025-26.xls
      DGCI&S "Yearly Time Series On Export including re-export By Commodity
      (6 digit)". Values are in US$ (no INR in these downloads).
  district_2025_26/dgcis_state_district_hs6_2025-26.zip
      29 DGCI&S "State of Origin" .xls files (State x District x HS6),
      Apr-2025 to Mar-2026, values in INR and US$.

Outputs (data/processed/):
  india_exports_hs6_fy2007_2026_long.csv   hs6 x FY, long format (non-zero rows)
  india_exports_hs6_fy2007_2026_wide.csv   hs6 x FY, wide, USD million
  hs6_descriptions.csv                     every (hs6, description) variant seen
  india_exports_national_totals.csv        national totals by FY (sanity check)
  district_exports_hs6_fy2025_26.parquet   State x District x HS6, FY 2025-26
  district_exports_state_totals_fy2025_26.csv

Run from repo root:  python scripts/01_clean_export_data.py
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

YEARLY_FILES = [
    RAW / "yearly_hs6" / "dgcis_yearly_hs6_2006-07_to_2015-16.xls",
    RAW / "yearly_hs6" / "dgcis_yearly_hs6_2016-17_to_2025-26.xls",
]
DISTRICT_ZIP = RAW / "district_2025_26" / "dgcis_state_district_hs6_2025-26.zip"


def clean_text(s: pd.Series) -> pd.Series:
    """Strip and collapse the runs of whitespace DGCI&S puts in descriptions."""
    return s.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)


# ---------------------------------------------------------------------------
# 1. Yearly HS6 time series (national)
# ---------------------------------------------------------------------------
def read_yearly(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, header=1, dtype={"HS CODE": str})
    df = df.rename(columns={"HS CODE": "hs6", "DESCRIPTION": "description"})
    df["hs6"] = df["hs6"].str.strip().str.zfill(6)
    assert df["hs6"].str.fullmatch(r"\d{6}").all(), "non-6-digit HS code found"
    df["description"] = clean_text(df["description"])
    long = df.melt(id_vars=["hs6", "description"], var_name="col", value_name="export_usd")
    long["fy"] = long["col"].str.extract(r"(\d{4}-\d{2})")[0]
    assert long["fy"].notna().all()
    long["source_file"] = path.name
    return long.drop(columns="col")


def build_yearly() -> pd.DataFrame:
    raw = pd.concat([read_yearly(p) for p in YEARLY_FILES], ignore_index=True)
    raw["export_usd"] = raw["export_usd"].fillna(0).astype("int64")

    # The two files cover disjoint years (2006-07..2015-16 and 2016-17..2025-26).
    years_per_file = raw.groupby("source_file")["fy"].unique()
    assert len(set(years_per_file.iloc[0]) & set(years_per_file.iloc[1])) == 0

    # Description lookup: the same HS6 code appears with several descriptions
    # (old vs new wording, HS 2007/2012/2017/2022 revisions). Keep every variant
    # with the FYs in which it carried non-zero trade.
    nz = raw[raw["export_usd"] > 0]
    desc = (
        nz.groupby(["hs6", "description"])
        .agg(first_fy=("fy", "min"), last_fy=("fy", "max"), total_usd=("export_usd", "sum"))
        .reset_index()
        .sort_values(["hs6", "last_fy", "total_usd"], ascending=[True, False, False])
    )
    # Preferred description per code = the one used most recently.
    latest_desc = desc.drop_duplicates("hs6").set_index("hs6")["description"]

    # Within one file, a code's description variants never both carry trade in
    # the same year (checked), so summing over descriptions is lossless.
    long = raw.groupby(["hs6", "fy"], as_index=False)["export_usd"].sum()
    long = long[long["export_usd"] != 0].copy()
    long["fy_end_year"] = long["fy"].str[:4].astype(int) + 1  # FY 2025-26 -> 2026
    long["export_usd_mn"] = long["export_usd"] / 1e6
    long["hs2"] = long["hs6"].str[:2]
    long["hs4"] = long["hs6"].str[:4]
    long["description"] = long["hs6"].map(latest_desc)
    long = long[["hs6", "hs4", "hs2", "description", "fy", "fy_end_year", "export_usd", "export_usd_mn"]]
    long = long.sort_values(["hs6", "fy"]).reset_index(drop=True)

    long.to_csv(OUT / "india_exports_hs6_fy2007_2026_long.csv", index=False)

    wide = long.pivot_table(index="hs6", columns="fy", values="export_usd_mn", aggfunc="sum", fill_value=0)
    wide.columns = [f"FY{c}" for c in wide.columns]
    wide.insert(0, "description", latest_desc.reindex(wide.index))
    wide.round(6).to_csv(OUT / "india_exports_hs6_fy2007_2026_wide.csv")

    desc.assign(total_usd_mn=desc["total_usd"] / 1e6).drop(columns="total_usd").to_csv(
        OUT / "hs6_descriptions.csv", index=False
    )

    totals = long.groupby("fy", as_index=False).agg(
        n_hs6=("hs6", "nunique"), export_usd_bn=("export_usd", lambda s: s.sum() / 1e9)
    )
    totals.round(4).to_csv(OUT / "india_exports_national_totals.csv", index=False)
    print("National totals by FY (USD bn):\n", totals.round(2).to_string(index=False))
    return long


# ---------------------------------------------------------------------------
# 2. State x District x HS6, FY 2025-26
# ---------------------------------------------------------------------------
DISTRICT_COLS = {
    0: "state",
    1: "district",
    2: "hs6",
    3: "description",
    4: "mar2026_inr",
    5: "mar2026_usd",
    6: "export_inr",
    7: "export_usd",
}


def build_district() -> pd.DataFrame:
    frames = []
    with zipfile.ZipFile(DISTRICT_ZIP) as zf:
        # Member names use Windows backslashes; sort by trailing part number.
        members = sorted(zf.namelist(), key=lambda n: int(re.search(r"_(\d+)\.xls$", n).group(1)))
        for name in members:
            buf = io.BytesIO(zf.read(name))
            title = pd.read_excel(buf, header=None, nrows=1).iloc[0, 0]
            assert "Apr-2025 To Mar-2026" in title, title
            buf.seek(0)
            df = pd.read_excel(buf, header=None, skiprows=2, dtype={2: str})
            df = df.rename(columns=DISTRICT_COLS)
            df["source_part"] = int(re.search(r"_(\d+)\.xls$", name).group(1))
            frames.append(df)
    d = pd.concat(frames, ignore_index=True)
    n_raw = len(d)

    d["state"] = clean_text(d["state"]).str.upper()
    d["district"] = clean_text(d["district"]).str.upper()
    d["description"] = clean_text(d["description"])
    d["hs6"] = d["hs6"].str.strip().str.zfill(6)
    assert d["hs6"].str.fullmatch(r"\d{6}").all()
    for c in ["mar2026_inr", "mar2026_usd", "export_inr", "export_usd"]:
        d[c] = pd.to_numeric(d[c], errors="raise").fillna(0).astype("int64")

    dups = d.duplicated(["state", "district", "hs6", "description"]).sum()
    print(f"District rows: {n_raw:,}; exact key duplicates: {dups}")

    d["hs4"] = d["hs6"].str[:4]
    d["hs2"] = d["hs6"].str[:2]
    d["fy"] = "2025-26"
    d["export_usd_mn"] = d["export_usd"] / 1e6
    d = d[
        ["fy", "state", "district", "hs6", "hs4", "hs2", "description",
         "export_usd", "export_usd_mn", "export_inr", "mar2026_usd", "mar2026_inr", "source_part"]
    ].sort_values(["state", "district", "hs6"]).reset_index(drop=True)

    d.to_parquet(OUT / "district_exports_hs6_fy2025_26.parquet", index=False, compression="zstd")

    st = (
        d.groupby("state", as_index=False)
        .agg(n_districts=("district", "nunique"), n_hs6=("hs6", "nunique"),
             export_usd_mn=("export_usd_mn", "sum"), export_inr_cr=("export_inr", lambda s: s.sum() / 1e7))
        .sort_values("export_usd_mn", ascending=False)
    )
    st.round({"export_usd_mn": 3, "export_inr_cr": 2}).to_csv(
        OUT / "district_exports_state_totals_fy2025_26.csv", index=False
    )
    print(f"District file total FY2025-26: USD {d['export_usd'].sum()/1e9:,.2f} bn, "
          f"{d['state'].nunique()} states/UTs, {d[['state','district']].drop_duplicates().shape[0]} districts")
    return d


if __name__ == "__main__":
    yearly = build_yearly()
    district = build_district()
    nat_fy26 = yearly.loc[yearly["fy"] == "2025-26", "export_usd"].sum() / 1e9
    print(f"Check: national FY2025-26 (yearly file) = USD {nat_fy26:,.2f} bn vs "
          f"district file = USD {district['export_usd'].sum()/1e9:,.2f} bn")
