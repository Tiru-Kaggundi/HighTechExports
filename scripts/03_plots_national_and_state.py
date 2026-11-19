"""
Step 03 - Charts: national time series (FY2006-07 .. FY2025-26) and states (FY2025-26).

Headline definition: high-tech exports (OECD list, partial SITC codes weighted)
as % of manufactured exports (World Bank: SITC 5-8 excl. 68).

Outputs: figures/*.png  and  data/processed/state_summary_fy2025_26.csv
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

# Validated categorical palette (light mode), fixed order.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
OTHER = "#a3a29c"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.titlelocation": "left", "axes.titlesize": 13, "axes.titleweight": "bold",
})
SOURCE = "Source: DGCI&S export data; WITS HS→SITC Rev.3 concordances; OECD (1997) high-tech product list."


def fy_label(fy: str) -> str:  # "2025-26" -> "FY26"
    return "FY" + fy[-2:]


def finish(fig, ax, name: str, note: str = SOURCE) -> None:
    fig.text(0.01, 0.01, note, fontsize=7.5, color=INK2, ha="left", va="bottom")
    fig.savefig(FIG / name, dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
nat = pd.read_csv(PROC / "india_hightech_share_national.csv")
nat["lab"] = nat["fy"].map(fy_label)
x = range(len(nat))

# 1. Headline share --------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.plot(x, nat["hightech_pct_of_manuf_wdi"], color=SERIES[0], lw=2, marker="o", ms=4,
        label="% of manufactured exports (World Bank: SITC 5–8 excl. 68)")
ax.plot(x, nat["hightech_pct_of_manuf_unctad"], color=SERIES[1], lw=2, ls="--",
        label="Sensitivity: also excluding gems & precious stones (667)")
for i in [0, len(nat) - 1]:
    v = nat["hightech_pct_of_manuf_wdi"].iloc[i]
    ax.annotate(f"{v:.1f}%", (i, v), textcoords="offset points", xytext=(0, -16) if i == 0 else (-4, -18),
                ha="center", fontsize=9, color=INK, fontweight="bold")
ax.set_xticks(list(x), nat["lab"], rotation=0, fontsize=8)
ax.set_ylim(0, max(nat["hightech_pct_of_manuf_unctad"]) * 1.15)
ax.set_ylabel("High-tech share (%)")
ax.set_title("India: high-tech exports as a share of manufactured exports")
ax.legend(frameon=False, loc="upper left", fontsize=8.5)
finish(fig, ax, "01_hightech_share_national.png")

# 2. High-tech exports by OECD group (stacked bars, US$ bn) ----------------
grp = pd.read_csv(PROC / "india_hightech_by_group_national.csv", index_col=0) / 1000
main = ["Electronics-telecommunications", "Aerospace", "Chemistry", "Pharmacy",
        "Scientific instruments", "Computers-office machines"]
grp["Other (electrical & non-electrical machinery, armament)"] = grp.drop(columns=main).sum(axis=1)
grp = grp[main + ["Other (electrical & non-electrical machinery, armament)"]]
fig, ax = plt.subplots(figsize=(9, 5.2))
bottom = pd.Series(0.0, index=grp.index)
colors = SERIES[:6] + [OTHER]
for col, c in zip(grp.columns, colors):
    ax.bar(list(x), grp[col].values, bottom=bottom.values, color=c, width=0.72, label=col,
           edgecolor=SURFACE, linewidth=1)
    bottom += grp[col]
for i, tot in enumerate(bottom.values):
    if i in (0, len(bottom) - 1) or i % 3 == 0:
        ax.text(i, tot + 0.8, f"{tot:.0f}", ha="center", fontsize=8, color=INK2)
ax.set_xticks(list(x), [fy_label(f) for f in grp.index], fontsize=8)
ax.set_ylabel("US$ billion")
ax.set_title("India: high-tech exports by product group (US$ bn)")
ax.legend(frameon=False, fontsize=8, loc="upper left", reverse=True)
ax.grid(axis="x", visible=False)
finish(fig, ax, "02_hightech_by_group_national.png")

# 3. Manufactured vs high-tech value (same unit, one axis) -----------------
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.plot(x, nat["manuf_wdi_usd_mn"] / 1000, color=SERIES[0], lw=2, label="Manufactured exports")
ax.plot(x, nat["hightech_usd_mn"] / 1000, color=SERIES[1], lw=2, label="High-tech exports")
ax.plot(x, nat["total_exports_usd_mn"] / 1000, color=OTHER, lw=1.5, ls=":", label="Total merchandise exports")
for col, c in [("manuf_wdi_usd_mn", SERIES[0]), ("hightech_usd_mn", SERIES[1]), ("total_exports_usd_mn", INK2)]:
    v = nat[col].iloc[-1] / 1000
    ax.annotate(f"{v:.0f}", (len(nat) - 1, v), textcoords="offset points", xytext=(6, -3), fontsize=8.5, color=INK)
ax.set_xticks(list(x), nat["lab"], fontsize=8)
ax.set_ylabel("US$ billion")
ax.set_ylim(0)
ax.set_title("India: total, manufactured and high-tech exports (US$ bn)")
ax.legend(frameon=False, loc="upper left", fontsize=8.5)
finish(fig, ax, "03_exports_levels_national.png")

# 6. Manufactured exports as % of total exports ----------------------------
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.plot(x, nat["manuf_wdi_pct_of_total"], color=SERIES[0], lw=2, marker="o", ms=4,
        label="Manufactured (World Bank: SITC 5–8 excl. 68)")
unctad_pct = 100 * nat["manuf_unctad_usd_mn"] / nat["total_exports_usd_mn"]
ax.plot(x, unctad_pct, color=SERIES[1], lw=2, ls="--",
        label="Sensitivity: also excluding gems & precious stones (667)")
for i in [0, len(nat) - 1]:
    v = nat["manuf_wdi_pct_of_total"].iloc[i]
    ax.annotate(f"{v:.1f}%", (i, v), textcoords="offset points", xytext=(0, 9), ha="center",
                fontsize=9, color=INK, fontweight="bold")
ax.set_xticks(list(x), nat["lab"], fontsize=8)
ax.set_ylim(0, 100)
ax.set_ylabel("% of total merchandise exports")
ax.set_title("India: manufactured exports as a share of total merchandise exports")
ax.legend(frameon=False, loc="lower left", fontsize=8.5)
finish(fig, ax, "06_manuf_share_of_total_national.png")

# ---------------------------------------------------------------------------
st = pd.read_csv(PROC / "hightech_share_by_state_fy2025_26.csv")
st["state_label"] = st["state"].str.title().str.replace("Dadra,Nh,Daman,Diu", "DNH & DD", regex=False)
summary = st[["state", "total_exports_usd_mn", "manuf_wdi_usd_mn", "hightech_usd_mn",
              "hightech_pct_of_manuf_wdi", "hightech_pct_of_manuf_unctad"]].copy()
summary["share_of_india_hightech_pct"] = 100 * summary["hightech_usd_mn"] / summary["hightech_usd_mn"].sum()
summary.sort_values("hightech_usd_mn", ascending=False).round(3).to_csv(
    PROC / "state_summary_fy2025_26.csv", index=False)

# Only states with meaningful manufactured exports (>= US$ 500 mn), excl. UNSPECIFIED.
big = st[(st["manuf_wdi_usd_mn"] >= 500) & (st["state"] != "UNSPECIFIED")]
STATE_NOTE = (SOURCE + "\nStates with manufactured exports ≥ US$ 0.5 bn. State = DGCI&S 'state of origin'; "
              "Delhi likely reflects goods registered/consolidated there rather than made there.")

# 4. State high-tech share -------------------------------------------------
s = big.sort_values("hightech_pct_of_manuf_wdi")
india = 100 * st["hightech_usd_mn"].sum() / st["manuf_wdi_usd_mn"].sum()
fig, ax = plt.subplots(figsize=(8, 0.32 * len(s) + 1.4))
ax.barh(s["state_label"], s["hightech_pct_of_manuf_wdi"], color=SERIES[0], height=0.66)
for yi, v in enumerate(s["hightech_pct_of_manuf_wdi"]):
    ax.text(v + 0.6, yi, f"{v:.1f}%", va="center", fontsize=8, color=INK)
ax.axvline(india, color=INK2, lw=1, ls="--", zorder=0)
ax.text(india + 0.5, -1.0, f"India average {india:.1f}%", fontsize=8, color=INK2, va="center")
ax.set_ylim(-1.6, len(s) - 0.4)
ax.set_xlabel("High-tech exports as % of the state's manufactured exports")
ax.set_title("High-tech share of manufactured exports by state, FY 2025-26")
ax.grid(axis="y", visible=False)
ax.tick_params(axis="y", length=0, labelsize=8.5)
finish(fig, ax, "04_state_hightech_share_fy2026.png", STATE_NOTE)

# 5. State high-tech value -------------------------------------------------
s = big.sort_values("hightech_usd_mn")
fig, ax = plt.subplots(figsize=(8, 0.32 * len(s) + 1.4))
ax.barh(s["state_label"], s["hightech_usd_mn"] / 1000, color=SERIES[0], height=0.66)
for yi, v in enumerate(s["hightech_usd_mn"] / 1000):
    ax.text(v + 0.15, yi, f"{v:.1f}" if v >= 0.1 else f"{v:.2f}", va="center", fontsize=8, color=INK)
ax.set_xlabel("High-tech exports, US$ billion")
ax.set_title("High-tech exports by state, FY 2025-26 (US$ bn)")
ax.grid(axis="y", visible=False)
ax.tick_params(axis="y", length=0, labelsize=8.5)
finish(fig, ax, "05_state_hightech_value_fy2026.png", STATE_NOTE)

print("Wrote:", ", ".join(sorted(p.name for p in FIG.glob("*.png"))))
