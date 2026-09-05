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
        linewidth=1.1, edgecolor=edge, facecolor=edge, alpha=0.10,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9)


def arrow(ax, start, end):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="->", mutation_scale=11, linewidth=1.0))


def draw():
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    fig, ax = plt.subplots(figsize=(11.5, 5.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.02, 0.96, "(a) File-level reliability path", fontweight="bold", va="top")
    ax.text(0.56, 0.96, "(b) LiCSBAS-ready output and trace", fontweight="bold", va="top")

    labels = ["Resolve", "Check final / .part", "Range resume or restart", "Byte check", "Atomic final name"]
    y = [0.80, 0.64, 0.48, 0.32, 0.16]
    for label, yy in zip(labels, y):
        box(ax, (0.08, yy-0.055), (0.32, 0.11), label, colors[0])
    for y1, y2 in zip(y[:-1], y[1:]):
        arrow(ax, (0.24, y1-0.06), (0.24, y2+0.06))

    tree = (
        "FRAME/\n"
        "├── GEOC/\n"
        "│   ├── YYYYMMDD_YYYYMMDD/\n"
        "│   │   ├── *.geo.unw.tif\n"
        "│   │   └── *.geo.cc.tif\n"
        "│   └── geometry, MLI, baselines, metadata\n"
        "├── GACOS/  (optional)\n"
        "├── download_report.csv\n"
        "└── download.log"
    )
    ax.text(
        0.58, 0.80, tree, family="DejaVu Sans Mono", fontsize=9.5,
        ha="left", va="top",
        bbox=dict(boxstyle="round,pad=0.35", edgecolor=colors[1], facecolor=colors[1], alpha=0.08),
    )
    ax.text(
        0.58, 0.20,
        "Required pair products are validated separately from optional corrections.\n"
        "A bounded benchmark was accepted by LiCSBAS step 02 without renaming.",
        ha="left", va="top", fontsize=8.5,
    )
    fig.tight_layout()
    for ext in ("png", "pdf"):
        kwargs = {"dpi": 600} if ext == "png" else {}
        fig.savefig(OUT / f"Figure_2_Download_Reliability_and_Directory.{ext}", bbox_inches="tight", **kwargs)
    plt.close(fig)


if __name__ == "__main__":
    draw()
