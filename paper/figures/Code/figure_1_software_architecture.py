from __future__ import annotations

from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "Final"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
})


def rounded_box(ax, x, y, w, h, text, color, lw=1.1):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        linewidth=lw,
        edgecolor=color,
        facecolor=color,
        alpha=0.10,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9)
    return patch


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="-|>", mutation_scale=12,
        linewidth=1.0, shrinkA=2, shrinkB=2,
    ))


def draw():
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    c_data, c_plan = colors[0], colors[1]

    fig, ax = plt.subplots(figsize=(11.5, 4.8))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Main acquisition path
    y_top, w, h = 0.61, 0.19, 0.19
    xs = [0.035, 0.285, 0.535, 0.785]
    labels = [
        "LiCSAR portal\nresources",
        "Discover and\nresolve",
        "Transfer, resume\nand finalise",
        "GEOC output\nand reports",
    ]
    for x, label in zip(xs, labels):
        rounded_box(ax, x, y_top, w, h, label, c_data)
    for a, b in zip(xs[:-1], xs[1:]):
        arrow(ax, a + w, y_top + h / 2, b, y_top + h / 2)

    # Planning and validation branch
    y_bot = 0.20
    bx = [0.285, 0.535, 0.785]
    blabels = [
        "Multi-frame\ntemporal planner",
        "Structural and\nnetwork checks",
        "LiCSBAS step 02\nvalidation",
    ]
    for x, label in zip(bx, blabels):
        rounded_box(ax, x, y_bot, w, h, label, c_plan)
    arrow(ax, xs[0] + w / 2, y_top, bx[0] + w / 2, y_bot + h)
    arrow(ax, xs[2] + w / 2, y_top, bx[1] + w / 2, y_bot + h)
    arrow(ax, bx[0] + w, y_bot + h / 2, bx[1], y_bot + h / 2)
    arrow(ax, bx[1] + w, y_bot + h / 2, bx[2], y_bot + h / 2)

    # Small pathway keys only; scope limitations belong in the caption/table.
    ax.text(0.035, 0.875, "Acquisition path", color=c_data, fontsize=8.5, fontweight="bold")
    ax.text(0.285, 0.115, "Planning and validation", color=c_plan, fontsize=8.5, fontweight="bold")

    fig.tight_layout(pad=0.6)
    for ext in ("png", "pdf"):
        kwargs = {"dpi": 600} if ext == "png" else {}
        fig.savefig(OUT / f"Figure_1_Software_Architecture.{ext}", bbox_inches="tight", **kwargs)
    plt.close(fig)


if __name__ == "__main__":
    draw()
