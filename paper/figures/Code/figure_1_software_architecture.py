from __future__ import annotations

from pathlib import Path
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "Source_Data"
OUT = HERE.parent / "Final"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})

from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


def box(ax, xy, size, text, edge):
    x, y = xy
    w, h = size
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.006",
        linewidth=1.2, edgecolor=edge, facecolor=edge, alpha=0.12,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9)
    return patch


def arrow(ax, start, end):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="->", mutation_scale=12, linewidth=1.1))


def draw():
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    fig, ax = plt.subplots(figsize=(12.0, 5.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    w, h = 0.18, 0.20
    y1, y2 = 0.62, 0.22
    x = [0.03, 0.28, 0.53, 0.78]
    box(ax, (x[0], y1), (w, h), "LiCSAR portal\nlistings and objects", colors[0])
    box(ax, (x[1], y1), (w, h), "Discovery and\nresource resolution", colors[0])
    box(ax, (x[2], y1), (w, h), "Resumable transfer\nand finalisation", colors[0])
    box(ax, (x[3], y1), (w, h), "GEOC directory,\nreports and manifest", colors[0])
    box(ax, (x[1], y2), (w, h), "Inventory-only\nmulti-frame planner", colors[1])
    box(ax, (x[2], y2), (w, h), "Structural and\nnetwork validation", colors[1])
    box(ax, (x[3], y2), (w, h), "LiCSBAS step 02\n(bounded validation)", colors[1])

    arrow(ax, (x[0]+w, y1+h/2), (x[1], y1+h/2))
    arrow(ax, (x[1]+w, y1+h/2), (x[2], y1+h/2))
    arrow(ax, (x[2]+w, y1+h/2), (x[3], y1+h/2))
    arrow(ax, (x[0]+w/2, y1), (x[1]+w/2, y2+h))
    arrow(ax, (x[2]+w/2, y1), (x[2]+w/2, y2+h))
    arrow(ax, (x[2]+w, y2+h/2), (x[3], y2+h/2))

    ax.text(
        0.03, 0.06,
        "Outside scope: interferogram generation, inversion, mosaicking, "
        "cross-frame reference correction, and LOS decomposition.",
        ha="left", va="center", fontsize=8.5,
    )
    fig.tight_layout()
    for ext in ("png", "pdf"):
        kwargs = {"dpi": 600} if ext == "png" else {}
        fig.savefig(OUT / f"Figure_1_Software_Architecture.{ext}", bbox_inches="tight", **kwargs)
    plt.close(fig)


if __name__ == "__main__":
    draw()
