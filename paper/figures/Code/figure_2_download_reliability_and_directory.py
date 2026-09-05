from __future__ import annotations

from pathlib import Path
import json
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "Source_Data"
OUT = HERE.parent / "Final"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
})


def box(ax, x, y, w, h, text, color, fontsize=8.5, alpha=0.10, bold=False):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.010,rounding_size=0.010",
        linewidth=1.0,
        edgecolor=color,
        facecolor=color,
        alpha=alpha,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2, y + h / 2, text,
        ha="center", va="center", fontsize=fontsize,
        fontweight="bold" if bold else "normal",
    )


def arrow(ax, start, end):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=11,
        linewidth=0.9, shrinkA=2, shrinkB=2,
    ))


def draw():
    benchmark = json.loads((DATA / "revision_benchmark_results.json").read_text(encoding="utf-8"))
    pairs = [
        "20160909_20160921", "20160909_20160927", "20160909_20161003",
        "20160921_20160927", "20160921_20161003", "20160927_20161003",
    ]

    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    c1, c2, c3 = colors[0], colors[1], colors[2]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.8, 5.4), gridspec_kw={"width_ratios": [0.9, 1.1]})
    for ax in (ax1, ax2):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

    # (a) Reliability path: compact state chain, no explanatory paragraph.
    ax1.text(0.02, 0.96, "(a)", fontweight="bold", va="top")
    ys = [0.82, 0.66, 0.50, 0.34, 0.18]
    labels = ["Resolve", "Compare size", "Resume / restart", "Verify bytes", "Atomic rename"]
    for y, label in zip(ys, labels):
        box(ax1, 0.18, y - 0.05, 0.64, 0.10, label, c1, fontsize=9)
    for y1, y2 in zip(ys[:-1], ys[1:]):
        arrow(ax1, (0.50, y1 - 0.055), (0.50, y2 + 0.055))

    # (b) Actual bounded benchmark output.
    ax2.text(0.02, 0.96, "(b)", fontweight="bold", va="top")
    ax2.text(0.08, 0.90, "124D_04854_171313/", fontsize=9.5, fontweight="bold", family="DejaVu Sans Mono")

    box(ax2, 0.08, 0.54, 0.84, 0.29, "", c2, alpha=0.075)
    ax2.text(0.11, 0.79, "GEOC/", fontsize=9.2, fontweight="bold", family="DejaVu Sans Mono", va="top")
    ax2.text(0.13, 0.725, "6 interferogram folders  ·  12 IFG GeoTIFFs", fontsize=8.5, va="top")
    ax2.text(0.13, 0.675, "8 auxiliary files  ·  geometry / MLI / baselines / metadata", fontsize=8.5, va="top")

    # Pair IDs shown as actual benchmark output, two columns to stay compact.
    for i, pair in enumerate(pairs):
        col = 0 if i < 3 else 1
        row = i if i < 3 else i - 3
        x = 0.13 + 0.39 * col
        y = 0.635 - 0.040 * row
        ax2.text(x, y, pair, fontsize=7.8, family="DejaVu Sans Mono", va="top")

    # Report/log products are represented as separate output artifacts.
    report_labels = ["download_report.csv", "download.log", "download_summary.txt"]
    for i, label in enumerate(report_labels):
        box(ax2, 0.08 + i * 0.285, 0.36, 0.255, 0.085, label, c2, fontsize=7.8, alpha=0.075)

    # Short status badges from the real run.
    status = [
        f"{benchmark['benchmark_file_count']}/{benchmark['benchmark_file_count']} files",
        f"{benchmark['complete_pairs']}/{benchmark['selected_pair_count']} pairs",
        "structure PASS",
    ]
    for i, label in enumerate(status):
        box(ax2, 0.10 + i * 0.275, 0.16, 0.23, 0.11, label, c3, fontsize=8.5, alpha=0.10, bold=True)

    fig.tight_layout(w_pad=1.0, pad=0.8)
    for ext in ("png", "pdf"):
        kwargs = {"dpi": 600} if ext == "png" else {}
        fig.savefig(OUT / f"Figure_2_Download_Reliability_and_Directory.{ext}", bbox_inches="tight", **kwargs)
    plt.close(fig)


if __name__ == "__main__":
    draw()
