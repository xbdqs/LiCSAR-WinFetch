from __future__ import annotations

from pathlib import Path
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "Source_Data"
OUT = HERE.parent / "Final"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})

import json
import pandas as pd
import matplotlib.dates as mdates


def draw():
    epochs = pd.read_csv(DATA / "epoch_inventory.csv", dtype=str)
    frames = pd.read_csv(DATA / "frame_summary.csv", dtype={"first_epoch": str, "last_epoch": str})
    results = json.loads((DATA / "qilian_results_final.json").read_text(encoding="utf-8"))
    isolated_path = DATA / "Reviewer1_C7_106D_Isolated_Common_Epochs.csv"
    isolated = pd.read_csv(isolated_path, dtype=str) if isolated_path.is_file() else pd.DataFrame(columns=["isolated_common_epoch"])
    isolated_dates = pd.to_datetime(isolated.get("isolated_common_epoch", pd.Series(dtype=str)), format="%Y%m%d")
    epochs["date"] = pd.to_datetime(epochs["epoch"], format="%Y%m%d")

    # Put descending frames above ascending frames and preserve relative-orbit order.
    order = (
        frames.assign(direction_order=frames["direction"].map({"Ascending": 0, "Descending": 1}))
        .sort_values(["direction_order", "track_group", "frame"])["frame"].tolist()
    )
    frame_info = frames.set_index("frame")
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    color_map = {"Ascending": colors[0], "Descending": colors[1]}
    isolated_color = colors[2] if len(colors) > 2 else colors[0]

    fig, ax = plt.subplots(figsize=(11.5, 7.6))
    for y, frame in enumerate(order):
        dates = epochs.loc[epochs["frame"] == frame, "date"].sort_values()
        direction = frame_info.loc[frame, "direction"]
        ax.plot(dates, [y] * len(dates), marker="o", markersize=1.7, linewidth=0.45,
                color=color_map[direction])

    # Reviewer-revision annotation: the three common dates that become isolated
    # nodes when the 106D exact-common-pair edge intersection is imposed.
    for frame in ("106D_05049_131313", "106D_05248_131313"):
        if frame in order and len(isolated_dates):
            y = order.index(frame)
            ax.scatter(isolated_dates, [y] * len(isolated_dates), marker="x", s=36, linewidths=1.3,
                       color=isolated_color,
                       label="106D isolated common epochs (exact common pairs)" if frame == "106D_05049_131313" else None,
                       zorder=5)

    start = pd.to_datetime(results["project_maximum_common_calendar_start"], format="%Y%m%d")
    end = pd.to_datetime(results["project_maximum_common_calendar_end"], format="%Y%m%d")
    ax.axvspan(start, end, alpha=0.10, label="22-frame common calendar interval")

    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=7.5)
    ax.set_xlabel("Acquisition date")
    ax.set_ylabel("LiCSAR frame")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="x", linewidth=0.35, alpha=0.55)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.005), ncol=2, frameon=False, fontsize=8.2)
    ax.text(0.01, 0.015, "Blue: ascending; orange: descending", transform=ax.transAxes, fontsize=8)
    fig.autofmt_xdate(rotation=0)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        kwargs = {"dpi": 600} if ext == "png" else {}
        fig.savefig(OUT / f"Figure_3_Qilian_Temporal_Coverage.{ext}", bbox_inches="tight", **kwargs)
    plt.close(fig)


if __name__ == "__main__":
    draw()
