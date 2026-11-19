"""
Step 04 - Build a state/UT boundary GeoJSON matching the DGCI&S state names.

Source geometry: SHRUG (Development Data Lab) Census-2011 district polygons
(`india_districts_2011.shp`, pc11 codes), the same file used in the
dist_complexity_analysis repository. Its external boundary follows India's
official depiction (all of J&K incl. PoK, Gilgit-Baltistan and Aksai Chin).

Changes to reach today's states/UTs (as named in the DGCI&S data):
  * Telangana (2014) = Census-2011 AP districts Adilabad, Nizamabad,
    Karimnagar, Medak, Hyderabad, Rangareddy, Mahbubnagar, Nalgonda, Warangal,
    Khammam. (The 2014 transfer of 7 Khammam mandals to AP is ignored.)
  * Dadra & Nagar Haveli + Daman & Diu merged (2020) -> "DADRA,NH,DAMAN,DIU".
  * Jammu & Kashmir and Ladakh kept as ONE map unit "JAMMU AND KASHMIR + LADAKH":
    the file has no internal 2019 boundary for the un-named area of the state,
    and inventing one is avoided. Trade values of the two are summed for it.

Shared borders are simplified together (shapely.coverage_simplify) so states
stay gap-free. Output: data/reference/geo/india_states_official.geojson

Usage: python scripts/04_build_state_boundaries.py /path/to/india_districts_2011.shp
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import shapely

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reference" / "geo" / "india_states_official.geojson"

PC11_STATE = {
    "01": "JAMMU AND KASHMIR + LADAKH", "02": "HIMACHAL PRADESH", "03": "PUNJAB", "04": "CHANDIGARH",
    "05": "UTTARAKHAND", "06": "HARYANA", "07": "DELHI", "08": "RAJASTHAN", "09": "UTTAR PRADESH",
    "10": "BIHAR", "11": "SIKKIM", "12": "ARUNACHAL PRADESH", "13": "NAGALAND", "14": "MANIPUR",
    "15": "MIZORAM", "16": "TRIPURA", "17": "MEGHALAYA", "18": "ASSAM", "19": "WEST BENGAL",
    "20": "JHARKHAND", "21": "ODISHA", "22": "CHHATTISGARH", "23": "MADHYA PRADESH", "24": "GUJARAT",
    "25": "DADRA,NH,DAMAN,DIU", "26": "DADRA,NH,DAMAN,DIU", "27": "MAHARASHTRA", "28": "ANDHRA PRADESH",
    "29": "KARNATAKA", "30": "GOA", "31": "LAKSHADWEEP", "32": "KERALA", "33": "TAMIL NADU",
    "34": "PUDUCHERRY", "35": "ANDAMAN AND NICOBAR ISLANDS",
}
TELANGANA_2011 = {"Adilabad", "Nizamabad", "Karimnagar", "Medak", "Hyderabad", "Rangareddy",
                  "Mahbubnagar", "Nalgonda", "Warangal", "Khammam"}


def main(shp: str) -> None:
    d = gpd.read_file(shp)
    d["state"] = d["pc11_s_id"].map(PC11_STATE)
    assert d["state"].notna().all()
    tel = (d["pc11_s_id"] == "28") & d["d_name"].isin(TELANGANA_2011)
    assert tel.sum() == len(TELANGANA_2011)
    d.loc[tel, "state"] = "TELANGANA"

    st = d[["state", "geometry"]].dissolve(by="state").reset_index()
    st["geometry"] = st.geometry.make_valid()
    # Simplify all states together so neighbours keep identical shared edges.
    st["geometry"] = shapely.coverage_simplify(st.geometry.values, tolerance=0.01)
    # Snap to a 1e-4 degree grid (~11 m) so the rounded GeoJSON stays valid.
    st["geometry"] = shapely.set_precision(shapely.make_valid(st.geometry.values), 1e-4)
    assert st.geometry.is_valid.all()
    st = st.set_crs(4326, allow_override=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    st.to_file(OUT, driver="GeoJSON", COORDINATE_PRECISION=4)
    print(f"{len(st)} states/UTs -> {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         "/home/user/tiru-kaggundi/dist_complexity_analysis/data/geo/india_districts_2011.shp")
