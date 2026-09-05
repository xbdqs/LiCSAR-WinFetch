from __future__ import annotations

from pathlib import Path
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "Source_Data"
OUT = HERE.parent / "Final"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})

import pandas as pd
from matplotlib.patches import FancyBboxPatch


def draw():
    data = pd.read_csv(DATA / "validation_evidence.csv")
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    fig, ax = plt.subplots(figsize=(11.5, 5.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    lefts = [0.03, 0.27, 0.51, 0.75]
    for i, row in data.iterrows():
        x = lefts[i]
        patch = FancyBboxPatch(
            (x, 0.50), 0.20, 0.30, boxstyle="round,pad=0.012,rounding_size=0.006",
            linewidth=1.2, edgecolor=colors[2], facecolor=colors[2], alpha=0.11,
        )
        ax.add_patch(patch)
        ax.text(x + 0.10, 0.71, row["stage"], ha="center", va="center", fontweight="bold")
        ax.text(x + 0.10, 0.62, row["result"], ha="center", va="center", fontsize=9)
        ax.text(x + 0.10, 0.53, row["inference"], ha="center", va="center", fontsize=8)

    boundary = FancyBboxPatch(
        (0.10, 0.13), 0.80, 0.21, boxstyle="round,pad=0.012,rounding_size=0.006",
        linewidth=1.2, edgecolor=colors[3], facecolor=colors[3], alpha=0.10,
    )
    ax.add_patch(boundary)
    ax.text(0.50, 0.27, "Not established", ha="center", va="center", fontweight="bold")
    ax.text(
        0.50, 0.19,
        "global compatibility • speed superiority • pixel validity • inversion • cross-frame reference consistency",
        ha="center", va="center", fontsize=8.5,
    )
    fig.tight_layout()
    for ext in ("png", "pdf"):
        kwargs = {"dpi": 600} if ext == "png" else {}
        fig.savefig(OUT / f"Figure_4_Validation_Evidence_Boundary.{ext}", bbox_inches="tight", **kwargs)
    plt.close(fig)


if __name__ == "__main__":
    draw()
