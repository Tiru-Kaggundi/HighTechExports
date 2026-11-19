"""
Step 05 - State choropleths, FY 2025-26.

Boundaries: data/reference/geo/india_states_official.geojson (see script 04).
J&K and Ladakh are one map unit; their trade values are summed for it.
UNSPECIFIED (no state of origin) cannot be mapped and is left out.

Outputs: figures/07_map_state_hightech_share_fy2026.png
         figures/08_map_state_hightech_value_fy2026.png
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIG = ROOT / "figures"
GEO = ROOT / "data" / "reference" / "geo" / "india_states_official.geojson"

SURFACE, INK, INK2, NODATA, EDGE = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
# Sequential blue ramp (light -> dark), 7 classes.
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
MIN_MANUF_MN = 500  # states below this manufactured-export base are shown as "small base"
SOURCE = ("Source: DGCI&S state-of-origin exports FY 2025-26; WITS HS→SITC Rev.3; OECD (1997) high-tech list. "
          "Boundaries: SHRUG Census-2011 districts, re-aggregated to current states.\n"
          "J&K and Ladakh shown as one unit. State = DGCI&S 'state of origin' (Delhi likely reflects goods "
          "registered/consolidated there). US$ 4.3 bn with unspecified state not mapped.")

plt.rcParams.update({"figure.facecolor": SURFACE, "savefig.facecolor": SURFACE, "text.color": INK,
                     "font.size": 10, "axes.titlesize": 13, "axes.titleweight": "bold",
                     "axes.titlelocation": "left"})


def load() -> gpd.GeoDataFrame:
    st = pd.read_csv(PROC / "hightech_share_by_state_fy2025_26.csv")
    st["map_state"] = st["state"].replace({"JAMMU AND KASHMIR": "JAMMU AND KASHMIR + LADAKH",
                                           "LADAKH": "JAMMU AND KASHMIR + LADAKH"})
    st = st[st["state"] != "UNSPECIFIED"]
    agg = st.groupby("map_state", as_index=False)[["manuf_wdi_usd_mn", "hightech_usd_mn"]].sum()
    agg["share"] = 100 * agg["hightech_usd_mn"] / agg["manuf_wdi_usd_mn"]
    g = gpd.read_file(GEO).merge(agg, left_on="state", right_on="map_state", how="left")
    assert g["map_state"].notna().all(), g.loc[g["map_state"].isna(), "state"].tolist()
    return g.to_crs(7755)  # India-centred projection


def classify(v: pd.Series, bins: list[float]) -> pd.Series:
    return pd.cut(v, bins=bins, labels=False, include_lowest=True, right=False)


def draw(g, color_col, legend_items, title, fname, labels):
    fig, ax = plt.subplots(figsize=(8.5, 9.5))
    g.plot(ax=ax, color=g[color_col], edgecolor=EDGE, linewidth=0.6)
    small = g[g["_small"]] if "_small" in g else g.iloc[0:0]
    if len(small):
        small.plot(ax=ax, facecolor="none", edgecolor="#a3a29c", hatch="////", linewidth=0)
    for _, r in g[g["state"].isin(labels)].iterrows():
        p = r.geometry.representative_point()
        dx, dy = labels[r["state"]]
        txt = r["_label"]
        if (dx, dy) == (0, 0):
            ax.annotate(txt, (p.x, p.y), ha="center", va="center", fontsize=7.5, color=INK,
                        bbox=dict(boxstyle="round,pad=0.15", fc=SURFACE, ec="none", alpha=0.85))
        else:
            ax.annotate(txt, (p.x, p.y), xytext=(p.x + dx, p.y + dy), ha="left", va="center", fontsize=7.5,
                        color=INK, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6),
                        bbox=dict(boxstyle="round,pad=0.15", fc=SURFACE, ec="none", alpha=0.85))
    ax.set_axis_off()
    ax.set_title(title)
    ax.legend(handles=legend_items, loc="lower right", frameon=False, fontsize=8, title_fontsize=8.5,
              title=legend_items[0].get_label() and None)
    fig.text(0.02, 0.02, SOURCE, fontsize=6.8, color=INK2, ha="left", va="bottom")
    fig.savefig(FIG / fname, dpi=200, bbox_inches="tight")
    plt.close(fig)


def short(name: str) -> str:
    return {"DELHI": "Delhi", "TAMIL NADU": "Tamil Nadu", "KARNATAKA": "Karnataka",
            "UTTAR PRADESH": "UP", "MAHARASHTRA": "Maharashtra", "GUJARAT": "Gujarat",
            "TELANGANA": "Telangana", "HARYANA": "Haryana", "ANDHRA PRADESH": "AP", "GOA": "Goa",
            "WEST BENGAL": "WB", "RAJASTHAN": "Rajasthan", "ODISHA": "Odisha",
            "MADHYA PRADESH": "MP", "PUNJAB": "Punjab", "KERALA": "Kerala"}.get(name, name.title())


# Label placement: offset (metres in EPSG:7755) for small states, (0,0) = in place.
LABELS = {"DELHI": (-650_000, 250_000), "GOA": (-450_000, -50_000), "HARYANA": (-700_000, 80_000),
          "TAMIL NADU": (0, 0), "KARNATAKA": (0, 0), "UTTAR PRADESH": (0, 0), "MAHARASHTRA": (0, 0),
          "GUJARAT": (0, 0), "TELANGANA": (0, 0), "ANDHRA PRADESH": (0, 0), "WEST BENGAL": (0, 0),
          "RAJASTHAN": (0, 0), "ODISHA": (0, 0), "MADHYA PRADESH": (0, 0), "PUNJAB": (0, 0),
          "KERALA": (-450_000, -60_000)}

if __name__ == "__main__":
    g = load()

    # Map 1: high-tech share of manufactured exports
    bins = [0, 5, 10, 15, 20, 30, 40, 101]
    names = ["< 5%", "5–10%", "10–15%", "15–20%", "20–30%", "30–40%", "≥ 40%"]
    g["_small"] = g["manuf_wdi_usd_mn"] < MIN_MANUF_MN
    g["_cls"] = classify(g["share"], bins)
    g["_color"] = [NODATA if s else RAMP[int(c)] for s, c in zip(g["_small"], g["_cls"])]
    g["_label"] = [f"{short(s)} {v:.0f}%" for s, v in zip(g["state"], g["share"])]
    items = [Patch(facecolor=c, edgecolor="none", label=n) for c, n in zip(RAMP, names)]
    items.append(Patch(facecolor=NODATA, edgecolor="#a3a29c", hatch="////",
                       label="Manufactured exports < US$ 0.5 bn"))
    india = 100 * g["hightech_usd_mn"].sum() / g["manuf_wdi_usd_mn"].sum()
    draw(g, "_color", items,
         f"High-tech exports as % of manufactured exports, FY 2025-26\n(mapped states: {india:.1f}%)",
         "07_map_state_hightech_share_fy2026.png", LABELS)

    # Map 2: high-tech export value (US$ bn)
    vb = [0, 0.05, 0.25, 0.5, 1, 2.5, 5, 1e9]
    vnames = ["< 0.05", "0.05–0.25", "0.25–0.5", "0.5–1", "1–2.5", "2.5–5", "≥ 5"]
    g["_small"] = False
    v = g["hightech_usd_mn"] / 1000
    g["_color"] = [RAMP[int(c)] for c in classify(v, vb)]
    g["_label"] = [f"{short(s)} {x:.1f}" for s, x in zip(g["state"], v)]
    items = [Patch(facecolor=c, edgecolor="none", label=f"US$ {n} bn") for c, n in zip(RAMP, vnames)]
    draw(g, "_color", items, "High-tech exports by state, FY 2025-26 (US$ bn)",
         "08_map_state_hightech_value_fy2026.png", LABELS)
    print("Wrote maps 07, 08")
