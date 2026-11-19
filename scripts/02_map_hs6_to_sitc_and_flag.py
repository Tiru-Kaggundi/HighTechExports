"""
Step 02 - Map HS6 export codes to SITC Rev.3 and flag manufacturing and
high-technology exports.

Concordances: WITS (World Bank) HS -> SITC Rev.3 tables, one per HS edition
(data/raw/concordances_wits/Concordance_H{2..6}_to_S3.zip). Each HS6 code maps
to exactly one SITC Rev.3 code (5-digit, sometimes 4- or 3-digit).

HS edition per Indian FY is chosen from the data (share of export value whose
codes exist in each edition; see README):
    FY2006-07 .. FY2007-08 : HS2002 (H2)
    FY2008-09 .. FY2012-13 : HS2007 (H3)
    FY2013-14 .. FY2016-17 : HS2012 (H4)
    FY2017-18 .. FY2021-22 : HS2017 (H5)
    FY2022-23 .. FY2025-26 : HS2022 (H6)
A code not found in that year's edition is looked up in the other editions,
nearest first (codes reported a year early/late around a revision).

Flags
  manuf_wdi   SITC sections 5-8 excluding division 68 (non-ferrous metals)
              -> World Bank WDI definition of manufactures exports.
  manuf_unctad  same, also excluding group 667 (pearls, precious and
              semi-precious stones) -> UNCTAD/WITS "manufactured goods".
  hightech    OECD (Hatzichronoglou 1997, Annex 2 Table 4) SITC Rev.3 list,
              used by the World Bank for TX.VAL.TECH.* indicators
              (data/reference/oecd_hightech_sitc3.csv). Longest-prefix match:
              the most specific listed code wins (include or exclude).
  hightech_partial  SITC code is coarser than the list (e.g. concordance gives
              4-digit 7513 but only 75131/75132/75134 are high-tech) so some,
              but not all, of the product may be high-tech. Not counted as
              high-tech; reported for transparency.

Outputs (data/processed/):
  hs6_sitc3_concordance_flags.csv          every HS6 code per HS edition with SITC + flags
  india_exports_hs6_fy2007_2026_flagged.csv  yearly HS6 panel with SITC + flags
  india_hightech_share_national.csv        national manuf / high-tech totals and shares by FY
  india_hightech_by_group_national.csv     high-tech exports by OECD group by FY
  district_exports_hs6_fy2025_26_flagged.parquet
  hightech_share_by_state_fy2025_26.csv
  hightech_share_by_district_fy2025_26.csv
  unmapped_hs6_codes.csv                   codes with no SITC match (value by FY)
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONC_DIR = ROOT / "data" / "raw" / "concordances_wits"
REF = ROOT / "data" / "reference"
OUT = ROOT / "data" / "processed"

EDITIONS = ["H2", "H3", "H4", "H5", "H6"]
EDITION_LABEL = {"H2": "HS2002", "H3": "HS2007", "H4": "HS2012", "H5": "HS2017", "H6": "HS2022"}


def edition_for_fy(fy: str) -> str:
    start = int(fy[:4])
    if start <= 2007:
        return "H2"
    if start <= 2012:
        return "H3"
    if start <= 2016:
        return "H4"
    if start <= 2021:
        return "H5"
    return "H6"


# ---------------------------------------------------------------------------
# Concordances
# ---------------------------------------------------------------------------
def load_concordance(ed: str) -> pd.DataFrame:
    with zipfile.ZipFile(CONC_DIR / f"Concordance_{ed}_to_S3.zip") as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(name) as fh:
            c = pd.read_csv(fh, dtype=str, encoding="latin1")
    c.columns = ["hs6", "hs_description", "sitc3", "sitc3_description"]
    c["hs6"] = c["hs6"].str.strip().str.zfill(6)
    c["sitc3"] = c["sitc3"].str.strip()
    assert c["hs6"].is_unique, f"{ed}: HS6 codes not unique"
    c["hs_edition"] = ed
    return c


def add_manual_codes(conc: pd.DataFrame) -> pd.DataFrame:
    """Codes India reports that no WITS table covers: add them to every edition."""
    man = pd.read_csv(REF / "manual_hs6_sitc3_additions.csv", dtype=str)
    rows = []
    for ed in EDITIONS:
        have = set(conc.loc[conc["hs_edition"] == ed, "hs6"])
        add = man[~man["hs6"].isin(have)].assign(hs_edition=ed, hs_description="(manual) " + man["note"])
        rows.append(add[["hs6", "hs_description", "sitc3", "sitc3_description", "hs_edition"]])
    return pd.concat([conc] + rows, ignore_index=True)


def refine_coarse_codes(conc: pd.DataFrame) -> pd.DataFrame:
    """Where an edition maps an HS6 code to a coarse SITC code (3/4-digit) and
    another edition maps the SAME HS6 code to a finer SITC code that lies
    inside it (e.g. 776 -> 7764), use the finer code (nearest edition first).
    Codes that contradict the coarse one are never borrowed."""
    conc = conc.copy()
    conc["sitc3_wits"] = conc["sitc3"]
    conc["sitc3_refined_from"] = pd.NA
    by_code = {h: g for h, g in conc.groupby("hs6")}
    for i, row in conc[conc["sitc3"].str.len() < 5].iterrows():
        g = by_code[row["hs6"]]
        cand = g[(g["sitc3_wits"].str.len() > len(row["sitc3"]))
                 & g["sitc3_wits"].str.startswith(row["sitc3"])].copy()
        if cand.empty:
            continue
        here = EDITIONS.index(row["hs_edition"])
        cand["dist"] = cand["hs_edition"].map(lambda e: abs(EDITIONS.index(e) - here))
        best = cand.sort_values(["dist", "hs_edition"], ascending=[True, False]).iloc[0]
        conc.at[i, "sitc3"] = best["sitc3_wits"]
        conc.at[i, "sitc3_description"] = best["sitc3_description"]
        conc.at[i, "sitc3_refined_from"] = EDITION_LABEL[best["hs_edition"]]
    return conc


# ---------------------------------------------------------------------------
# Flags from SITC Rev.3 code
# ---------------------------------------------------------------------------
def load_hightech_list() -> pd.DataFrame:
    ht = pd.read_csv(REF / "oecd_hightech_sitc3.csv", dtype=str)
    assert ht["sitc3_prefix"].is_unique
    return ht


def hightech_lookup(sitc: str, ht: pd.DataFrame) -> tuple[str | None, bool]:
    """Return (high-tech group or None, partial flag)."""
    matches = ht[[sitc.startswith(p) for p in ht["sitc3_prefix"]]]
    group = None
    if len(matches):
        best = matches.loc[matches["sitc3_prefix"].str.len().idxmax()]
        if best["rule"] == "include":
            group = best["group"]
    partial = False
    if group is None:
        # Listed codes that are strictly finer than this SITC code.
        finer = ht[(ht["rule"] == "include") & ht["sitc3_prefix"].str.startswith(sitc)
                   & (ht["sitc3_prefix"].str.len() > len(sitc))]
        partial = len(finer) > 0
    return group, partial


def add_flags(c: pd.DataFrame, ht: pd.DataFrame) -> pd.DataFrame:
    s = c["sitc3"]
    c["sitc_section"] = s.str[0]
    c["sitc_division"] = s.str[:2]
    c["sitc_group"] = s.str[:3]
    in_5_8 = c["sitc_section"].isin(list("5678"))
    c["manuf_wdi"] = in_5_8 & (c["sitc_division"] != "68")
    c["manuf_unctad"] = c["manuf_wdi"] & (c["sitc_group"] != "667")
    lk = {code: hightech_lookup(code, ht) for code in s.unique()}
    c["hightech_group"] = s.map(lambda x: lk[x][0])
    c["hightech"] = c["hightech_group"].notna()
    c["hightech_partial"] = s.map(lambda x: lk[x][1])
    # All OECD high-tech products sit inside SITC 5-8 excl. 68 and 667.
    assert not (c["hightech"] & ~c["manuf_unctad"]).any()
    return c


FLAG_COLS = ["sitc3", "sitc3_wits", "sitc3_refined_from", "sitc3_description", "sitc_section", "sitc_division", "sitc_group",
             "manuf_wdi", "manuf_unctad", "hightech", "hightech_group", "hightech_partial"]


def attach(df: pd.DataFrame, conc: pd.DataFrame) -> pd.DataFrame:
    """Attach SITC + flags to rows with columns hs6, fy using edition order."""
    df = df.copy()
    df["hs_edition_target"] = df["fy"].map(edition_for_fy)
    out_parts = []
    remaining = df
    # Search order per target edition: itself, then nearest editions.
    for step in range(len(EDITIONS)):
        if remaining.empty:
            break
        ed_try = remaining["hs_edition_target"].map(
            lambda t: sorted(EDITIONS, key=lambda e: (abs(EDITIONS.index(e) - EDITIONS.index(t)),
                                                      -EDITIONS.index(e)))[step]
        )
        remaining = remaining.assign(hs_edition_used=ed_try)
        m = remaining.merge(conc, left_on=["hs6", "hs_edition_used"], right_on=["hs6", "hs_edition"],
                            how="left", indicator=True)
        hit = m["_merge"] == "both"
        out_parts.append(m[hit].drop(columns=["_merge", "hs_edition", "hs_description"]))
        remaining = m[~hit][df.columns]
    if not remaining.empty:
        out_parts.append(remaining.assign(hs_edition_used=pd.NA))
    res = pd.concat(out_parts, ignore_index=True)
    for col in ["manuf_wdi", "manuf_unctad", "hightech", "hightech_partial"]:
        res[col] = res[col].fillna(False).astype(bool)
    res["sitc_mapped"] = res["sitc3"].notna()
    res["hs_edition_used"] = res["hs_edition_used"].map(EDITION_LABEL)
    return res.drop(columns="hs_edition_target")


def share_table(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    v = df["export_usd"] / 1e6
    t = (
        df.assign(
            total=v,
            manuf_wdi_v=v.where(df["manuf_wdi"], 0),
            manuf_unctad_v=v.where(df["manuf_unctad"], 0),
            hightech_v=v.where(df["hightech"], 0),
            partial_v=v.where(df["hightech_partial"], 0),
            unmapped_v=v.where(~df["sitc_mapped"], 0),
        )
        .groupby(by, as_index=False)[["total", "manuf_wdi_v", "manuf_unctad_v", "hightech_v",
                                       "partial_v", "unmapped_v"]].sum()
        .rename(columns={
            "total": "total_exports_usd_mn",
            "manuf_wdi_v": "manuf_wdi_usd_mn",
            "manuf_unctad_v": "manuf_unctad_usd_mn",
            "hightech_v": "hightech_usd_mn",
            "partial_v": "hightech_partial_usd_mn",
            "unmapped_v": "unmapped_usd_mn",
        })
    )
    t["hightech_pct_of_manuf_wdi"] = 100 * t["hightech_usd_mn"] / t["manuf_wdi_usd_mn"]
    t["hightech_pct_of_manuf_unctad"] = 100 * t["hightech_usd_mn"] / t["manuf_unctad_usd_mn"]
    t["manuf_wdi_pct_of_total"] = 100 * t["manuf_wdi_usd_mn"] / t["total_exports_usd_mn"]
    return t.round(4)


def main() -> None:
    ht = load_hightech_list()
    conc = pd.concat([load_concordance(e) for e in EDITIONS], ignore_index=True)
    conc = add_manual_codes(conc)
    conc = refine_coarse_codes(conc)
    conc = add_flags(conc, ht)
    conc.assign(hs_edition=conc["hs_edition"].map(EDITION_LABEL))[
        ["hs_edition", "hs6", "hs_description"] + FLAG_COLS
    ].to_csv(OUT / "hs6_sitc3_concordance_flags.csv", index=False)

    # ---- National yearly panel ------------------------------------------
    y = pd.read_csv(OUT / "india_exports_hs6_fy2007_2026_long.csv", dtype={"hs6": str, "hs4": str, "hs2": str})
    yf = attach(y, conc).sort_values(["hs6", "fy"]).reset_index(drop=True)
    assert len(yf) == len(y) and yf["export_usd"].sum() == y["export_usd"].sum()
    yf.to_csv(OUT / "india_exports_hs6_fy2007_2026_flagged.csv", index=False)

    nat = share_table(yf, ["fy"])
    nat.to_csv(OUT / "india_hightech_share_national.csv", index=False)
    grp = (yf[yf["hightech"]].pivot_table(index="fy", columns="hightech_group", values="export_usd_mn",
                                          aggfunc="sum", fill_value=0).round(3))
    grp.to_csv(OUT / "india_hightech_by_group_national.csv")

    unm = (yf[~yf["sitc_mapped"]].pivot_table(index=["hs6", "description"], columns="fy",
                                              values="export_usd_mn", aggfunc="sum", fill_value=0))
    unm["total_usd_mn"] = unm.sum(axis=1)
    unm.sort_values("total_usd_mn", ascending=False).round(3).to_csv(OUT / "unmapped_hs6_codes.csv")

    # ---- District FY2025-26 ---------------------------------------------
    d = pd.read_parquet(OUT / "district_exports_hs6_fy2025_26.parquet")
    df_ = attach(d, conc)
    assert len(df_) == len(d)
    df_ = df_.sort_values(["state", "district", "hs6"]).reset_index(drop=True)
    df_.to_parquet(OUT / "district_exports_hs6_fy2025_26_flagged.parquet", index=False, compression="zstd")
    st = share_table(df_, ["state"]).sort_values("hightech_usd_mn", ascending=False)
    st.to_csv(OUT / "hightech_share_by_state_fy2025_26.csv", index=False)
    dt = share_table(df_, ["state", "district"]).sort_values("hightech_usd_mn", ascending=False)
    dt.to_csv(OUT / "hightech_share_by_district_fy2025_26.csv", index=False)

    pd.set_option("display.width", 200)
    print(nat[["fy", "total_exports_usd_mn", "manuf_wdi_usd_mn", "manuf_unctad_usd_mn", "hightech_usd_mn",
               "hightech_partial_usd_mn", "unmapped_usd_mn", "hightech_pct_of_manuf_wdi",
               "hightech_pct_of_manuf_unctad"]].round(1).to_string(index=False))
    print("\nEdition used (share of rows):\n", yf.groupby("fy")["hs_edition_used"].value_counts(normalize=True)
          .round(3).unstack().fillna(0).to_string())
    print("\nTop states FY2025-26:\n", st.head(12)[["state", "manuf_wdi_usd_mn", "hightech_usd_mn",
                                                  "hightech_pct_of_manuf_wdi"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
