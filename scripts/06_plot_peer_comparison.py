"""
Step 06 - Peer comparison: World Bank high-technology exports (% of manufactured
exports) for China, Vietnam, Malaysia, World and OECD members (calendar years).

India is left out on purpose: the World Bank series is by calendar year while
this project uses Indian financial years. (For reference, the World Bank's India
series tracks ours closely, e.g. 18.6% in 2024 vs 19.7% in FY 2024-25.)

Input : data/raw/worldbank_TX.VAL.TECH.MF.ZS.json  (World Bank API v2, downloaded 2026-11-20)
Output: data/processed/worldbank_hightech_share_peers.csv, figures/09_peer_hightech_share.png
        (FIG_DPI=300 -> figures/hires/)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DPI = int(os.environ.get("FIG_DPI", "200"))
FIG = ROOT / "figures" / ("hires" if DPI > 200 else "")
FIG.mkdir(parents=True, exist_ok=True)

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
SURFACE, INK, INK2, GRID, REF = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#7d7c77"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.titlelocation": "left", "axes.titlesize": 13, "axes.titleweight": "bold",
})

meta, rows = json.loads((ROOT / "data/raw/worldbank_TX.VAL.TECH.MF.ZS.json").read_text())
df = pd.DataFrame([{"iso3": r["countryiso3code"], "name": r["country"]["value"], "year": int(r["date"]),
                    "hightech_pct_of_manuf": r["value"]} for r in rows]).dropna()
df.sort_values(["iso3", "year"]).to_csv(ROOT / "data/processed/worldbank_hightech_share_peers.csv", index=False)
w = df.pivot(index="year", columns="iso3", values="hightech_pct_of_manuf").sort_index()

LINES = [  # (iso, label, color, style, width)
    ("MYS", "Malaysia", SERIES[2], "-", 2.2),
    ("VNM", "Vietnam", SERIES[1], "-", 2.2),
    ("CHN", "China", SERIES[0], "-", 2.2),
    ("WLD", "World", REF, "--", 1.6),
    ("OED", "OECD members", REF, ":", 1.8),
]
fig, ax = plt.subplots(figsize=(9, 5.2))
for iso, label, c, ls, lw in LINES:
    s = w[iso].dropna()
    ax.plot(s.index, s.values, color=c, ls=ls, lw=lw, label=label)
    ax.annotate(f"{label} {s.iloc[-1]:.0f}%", (s.index[-1], s.iloc[-1]), textcoords="offset points",
                xytext=(6, {"CHN": 6, "WLD": -6, "OED": -8}.get(iso, 0)), va="center", fontsize=8.5, color=INK)
    if iso == "VNM":
        ax.annotate(f"{s.iloc[0]:.0f}% in {s.index[0]}", (s.index[0], s.iloc[0]), textcoords="offset points",
                    xytext=(6, -10), fontsize=8, color=INK2)
ax.set_xlim(2007, 2027.5)
ax.set_xticks(range(2007, 2025, 2))
ax.set_ylim(0, 65)
ax.set_ylabel("High-tech exports, % of manufactured exports")
ax.set_title("High-tech share of manufactured exports: selected economies")
ax.legend(frameon=False, loc="upper left", fontsize=8.5, ncol=3)
fig.text(0.01, 0.01, "Source: World Bank, World Development Indicators (TX.VAL.TECH.MF.ZS), calendar years. "
         "Same OECD high-tech product list as used for India.", fontsize=7.5, color=INK2)
fig.savefig(FIG / "09_peer_hightech_share.png", dpi=DPI, bbox_inches="tight")
print("Wrote", FIG / "09_peer_hightech_share.png")
