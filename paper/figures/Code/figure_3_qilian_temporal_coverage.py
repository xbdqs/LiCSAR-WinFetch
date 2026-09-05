from __future__ import annotations

from pathlib import Path
import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "Source_Data"
OUT = HERE.parent / "Final"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
})


def draw():
    epochs = pd.read_csv(DATA / "epoch_inventory.csv", dtype=str)
    frames = pd.read_csv(DATA / "frame_summary.csv", dtype={"first_epoch": str, "last_epoch": str})
    results = json.loads((DATA / "qilian_results_final.json").read_text(encoding="utf-8"))
    isolated = pd.read_csv(DATA / "Reviewer1_C7_106D_Isolated_Common_Epochs.csv", dtype=str)

    epochs["date"] = pd.to_datetime(epochs["epoch"], format="%Y%m%d")
    isolated_dates = pd.to_datetime(isolated["isolated_common_epoch"], format="%Y%m%d")
    start = pd.to_datetime(results["project_maximum_common_calendar_start"], format="%Y%m%d")
    end = pd.to_datetime(results["project_maximum_common_calendar_end"], format="%Y%m%d")

    frame_info = frames.set_index("frame")
    asc = frames.loc[frames["direction"] == "Ascending"].sort_values(["track_group", "frame"])["frame"].tolist()
    desc = frames.loc[frames["direction"] == "Descending"].sort_values(["track_group", "frame"])["frame"].tolist()

    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    c_asc, c_desc, c_iso = colors[0], colors[1], colors[2]

    fig, (ax_a, ax_d) = plt.subplots(2, 1, figsize=(11.6, 7.8), sharex=True, gridspec_kw={"hspace": 0.09})

    def draw_panel(ax, order, color, panel_label):
        for y, frame in enumerate(order):
            dates = epochs.loc[epochs["frame"] == frame, "date"].sort_values()
            ax.plot(dates, [y] * len(dates), marker="o", markersize=1.6, linewidth=0.40, color=color, zorder=2)
        ax.axvspan(start, end, alpha=0.09, color=c_asc, zorder=0)
        ax.set_yticks(range(len(order)))
        ax.set_yticklabels(order, fontsize=7.4)
        ax.grid(axis="x", linewidth=0.35, alpha=0.45)
        ax.text(0.005, 0.97, panel_label, transform=ax.transAxes, ha="left", va="top", fontweight="bold")
        ax.set_ylim(-0.7, len(order) - 0.25)

    draw_panel(ax_a, asc, c_asc, "(a) Ascending")
    draw_panel(ax_d, desc, c_desc, "(b) Descending")

    # Reviewer-requested isolated common epochs in the 106D pair.
    for frame in ("106D_05049_131313", "106D_05248_131313"):
        if frame in desc:
            y = desc.index(frame)
            ax_d.scatter(isolated_dates, [y] * len(isolated_dates), marker="x", s=40, linewidths=1.4, color=c_iso, zorder=6)

    for dt_value in isolated_dates:
        ax_d.axvline(dt_value, linewidth=0.65, linestyle="--", alpha=0.30, color=c_iso, zorder=1)

    if "106D_05248_131313" in desc:
        y_label = desc.index("106D_05248_131313") + 0.28
        for dt_value in isolated_dates:
            ax_d.text(
                dt_value, y_label, dt_value.strftime("%Y-%m-%d"),
                rotation=28, ha="left", va="bottom", fontsize=7.0, color=c_iso, zorder=7,
            )

    ax_a.set_ylabel("LiCSAR frame")
    ax_d.set_ylabel("LiCSAR frame")
    ax_d.set_xlabel("Acquisition date")
    ax_d.xaxis.set_major_locator(mdates.YearLocator())
    ax_d.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # Compact keys using artists rather than explanatory prose.
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    handles = [
        Patch(facecolor=c_asc, alpha=0.09, edgecolor="none", label="22-frame maximum common calendar interval"),
        Line2D([0], [0], marker="x", linestyle="None", color=c_iso, markersize=7, markeredgewidth=1.4,
               label="106D isolated common epochs"),
    ]
    ax_a.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.015), ncol=2, frameon=False, fontsize=8.2)

    fig.subplots_adjust(left=0.18, right=0.99, bottom=0.08, top=0.91, hspace=0.09)
    for ext in ("png", "pdf"):
        kwargs = {"dpi": 600} if ext == "png" else {}
        fig.savefig(OUT / f"Figure_3_Qilian_Temporal_Coverage.{ext}", bbox_inches="tight", **kwargs)
    plt.close(fig)


if __name__ == "__main__":
    draw()
