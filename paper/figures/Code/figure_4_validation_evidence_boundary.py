from __future__ import annotations

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "Source_Data"
OUT = HERE.parent / "Final"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
})


def draw():
    data = pd.read_csv(DATA / "validation_evidence.csv")
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    c_ok, c_boundary = colors[2], colors[3]

    fig, ax = plt.subplots(figsize=(11.6, 4.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Validation ladder
    xs = [0.08, 0.22, 0.36, 0.50, 0.64, 0.78]
    y = 0.61
    ax.plot([xs[0], xs[-1]], [y, y], linewidth=1.2, color="0.55", zorder=0)

    for x, (_, row) in zip(xs, data.iterrows()):
        circle = Circle((x, y), 0.034, edgecolor=c_ok, facecolor=c_ok, alpha=0.16, linewidth=1.2)
        ax.add_patch(circle)
        ax.text(x, y, "✓", ha="center", va="center", fontsize=13, color=c_ok, fontweight="bold")
        ax.text(x, 0.46, row["stage"], ha="center", va="top", fontsize=8.1)
        result_text = str(row["result"]).replace("; ", "\n")
        ax.text(x, 0.34, result_text, ha="center", va="top", fontsize=8.8, fontweight="bold")

    # Explicit scope boundary after validated interoperability.
    boundary_x = 0.865
    ax.axvline(boundary_x, ymin=0.18, ymax=0.84, linestyle="--", linewidth=1.0, color=c_boundary, alpha=0.65)
    ax.text(boundary_x, 0.87, "validation boundary", ha="center", va="bottom", fontsize=8.0, color=c_boundary)

    box = FancyBboxPatch(
        (0.89, 0.28), 0.095, 0.39,
        boxstyle="round,pad=0.012,rounding_size=0.010",
        linewidth=1.0, edgecolor=c_boundary, facecolor=c_boundary, alpha=0.08,
    )
    ax.add_patch(box)
    ax.text(0.937, 0.59, "Not tested", ha="center", va="center", fontsize=8.5, fontweight="bold")
    ax.text(0.937, 0.46, "Step 03+\ninversion\nscientific inference", ha="center", va="center", fontsize=7.5)

    fig.tight_layout(pad=0.8)
    for ext in ("png", "pdf"):
        kwargs = {"dpi": 600} if ext == "png" else {}
        fig.savefig(OUT / f"Figure_4_Validation_Evidence_Boundary.{ext}", bbox_inches="tight", **kwargs)
    plt.close(fig)


if __name__ == "__main__":
    draw()
