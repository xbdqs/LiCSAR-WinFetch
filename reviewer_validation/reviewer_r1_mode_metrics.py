#!/usr/bin/env python3
"""Zero-download four-mode network comparison for Reviewer 1 comment 3.

Uses the archived Qilian epoch/pair inventories already distributed with the
repository. No network request is made and no LiCSAR raster is downloaded.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EPOCHS = ROOT / "paper" / "figures" / "Source_Data" / "epoch_inventory.csv"
DEFAULT_PAIRS = ROOT / "paper" / "figures" / "Source_Data" / "pair_inventory.csv"
DEFAULT_FRAMES = ("106D_05049_131313", "106D_05248_131313")


@dataclass(frozen=True)
class NetworkMetrics:
    node_count: int
    edge_count: int
    component_count: int
    largest_component_nodes: int
    isolated_node_count: int
    mean_degree: float
    edge_node_ratio: float
    cycle_rank: int
    max_temporal_gap_days: int | None
    median_baseline_days: float | None
    baseline_iqr_days: float | None


def _connected_components(nodes: set[str], edges: set[tuple[str, str]]) -> list[set[str]]:
    adj = {n: set() for n in nodes}
    for a, b in edges:
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)
    components: list[set[str]] = []
    seen: set[str] = set()
    for start in sorted(nodes):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        comp: set[str] = set()
        while stack:
            cur = stack.pop()
            comp.add(cur)
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        components.append(comp)
    return components


def _gap_days(nodes: Iterable[str]) -> int | None:
    dates = pd.to_datetime(sorted(set(nodes)), format="%Y%m%d")
    if len(dates) < 2:
        return None
    diffs = pd.Series(dates[1:] - dates[:-1]).dt.days
    return int(diffs.max())


def _metrics(nodes: set[str], pair_rows: pd.DataFrame) -> NetworkMetrics:
    edges = {
        (str(a), str(b))
        for a, b in zip(pair_rows["primary_epoch"], pair_rows["secondary_epoch"])
        if str(a) in nodes and str(b) in nodes
    }
    comps = _connected_components(nodes, edges)
    degree = {n: 0 for n in nodes}
    for a, b in edges:
        degree[a] += 1
        degree[b] += 1
    baselines = pd.to_numeric(pair_rows["temporal_baseline_days"], errors="coerce").dropna()
    median = float(baselines.median()) if len(baselines) else None
    iqr = float(baselines.quantile(0.75) - baselines.quantile(0.25)) if len(baselines) else None
    n = len(nodes)
    e = len(edges)
    c = len(comps)
    return NetworkMetrics(
        node_count=n,
        edge_count=e,
        component_count=c,
        largest_component_nodes=max((len(x) for x in comps), default=0),
        isolated_node_count=sum(1 for n0 in nodes if degree[n0] == 0),
        mean_degree=(2.0 * e / n) if n else 0.0,
        edge_node_ratio=(e / n) if n else 0.0,
        cycle_rank=e - n + c,
        max_temporal_gap_days=_gap_days(nodes),
        median_baseline_days=median,
        baseline_iqr_days=iqr,
    )


def _pair_filter(rows: pd.DataFrame, nodes: set[str]) -> pd.DataFrame:
    return rows[
        rows["primary_epoch"].astype(str).isin(nodes)
        & rows["secondary_epoch"].astype(str).isin(nodes)
    ].copy()


def compute(epoch_csv: Path, pair_csv: Path, frames: tuple[str, str]) -> tuple[pd.DataFrame, dict]:
    epochs = pd.read_csv(epoch_csv, dtype={"frame": str, "epoch": str})
    pairs = pd.read_csv(
        pair_csv,
        dtype={"frame": str, "pair": str, "primary_epoch": str, "secondary_epoch": str},
    )
    for frame in frames:
        if frame not in set(epochs["frame"]):
            raise ValueError(f"Frame missing from epoch inventory: {frame}")
        if frame not in set(pairs["frame"]):
            raise ValueError(f"Frame missing from pair inventory: {frame}")

    epoch_sets = {f: set(epochs.loc[epochs.frame == f, "epoch"].astype(str)) for f in frames}
    pair_rows = {f: pairs.loc[pairs.frame == f].copy() for f in frames}

    starts = {f: min(epoch_sets[f]) for f in frames}
    ends = {f: max(epoch_sets[f]) for f in frames}
    common_start = max(starts.values())
    common_end = min(ends.values())
    if common_start > common_end:
        raise ValueError("The selected frames have no common calendar interval")

    period_nodes = {
        f: {d for d in epoch_sets[f] if common_start <= d <= common_end}
        for f in frames
    }
    common_epochs = set.intersection(*(period_nodes[f] for f in frames))
    period_pairs = {f: _pair_filter(pair_rows[f], period_nodes[f]) for f in frames}
    common_pair_names = set.intersection(*(set(period_pairs[f]["pair"].astype(str)) for f in frames))

    rows: list[dict] = []
    mode_nodes: dict[tuple[str, str], set[str]] = {}
    mode_pairs: dict[tuple[str, str], pd.DataFrame] = {}

    for f in frames:
        mode_nodes[("independent", f)] = epoch_sets[f]
        mode_pairs[("independent", f)] = pair_rows[f]
        mode_nodes[("common-period", f)] = period_nodes[f]
        mode_pairs[("common-period", f)] = period_pairs[f]
        mode_nodes[("common-epochs", f)] = common_epochs
        mode_pairs[("common-epochs", f)] = _pair_filter(pair_rows[f], common_epochs)
        mode_nodes[("common-pairs", f)] = common_epochs
        mode_pairs[("common-pairs", f)] = period_pairs[f][period_pairs[f]["pair"].astype(str).isin(common_pair_names)].copy()

    for mode in ("independent", "common-period", "common-epochs", "common-pairs"):
        for f in frames:
            nodes = mode_nodes[(mode, f)]
            selected = mode_pairs[(mode, f)]
            m = _metrics(nodes, selected)
            base_nodes = len(epoch_sets[f])
            base_pairs = len(pair_rows[f])
            period_pair_count = len(period_pairs[f])
            row = {
                "mode": mode,
                "frame": f,
                "common_interval_start": common_start,
                "common_interval_end": common_end,
                **m.__dict__,
                "node_retention_vs_independent": m.node_count / base_nodes if base_nodes else None,
                "pair_retention_vs_independent": m.edge_count / base_pairs if base_pairs else None,
                "pair_retention_vs_common_period": m.edge_count / period_pair_count if period_pair_count else None,
            }
            rows.append(row)

    common_pair_rows = period_pairs[frames[0]][period_pairs[frames[0]]["pair"].astype(str).isin(common_pair_names)]
    cp_metrics = _metrics(common_epochs, common_pair_rows)
    cp_edges = {
        (str(a), str(b))
        for a, b in zip(common_pair_rows["primary_epoch"], common_pair_rows["secondary_epoch"])
    }
    degree = {n: 0 for n in common_epochs}
    for a, b in cp_edges:
        degree[a] += 1
        degree[b] += 1
    isolated = sorted(n for n, deg in degree.items() if deg == 0)

    summary = {
        "analysis": "Reviewer 1 comment 3 zero-download four-mode comparison",
        "frames": list(frames),
        "common_calendar_interval": [common_start, common_end],
        "common_epoch_count": len(common_epochs),
        "common_pair_count": len(common_pair_names),
        "common_pair_graph_component_count": cp_metrics.component_count,
        "common_pair_graph_largest_component_nodes": cp_metrics.largest_component_nodes,
        "common_pair_graph_isolated_epoch_count": cp_metrics.isolated_node_count,
        "isolated_common_epochs": isolated,
        "common_pair_retention_relative_to_smaller_common_period_network": (
            len(common_pair_names) / min(len(period_pairs[f]) for f in frames)
        ),
        "network_note": "Connectivity is topological only and does not imply coherence, unwrapping quality, atmospheric quality, or cross-frame reference consistency.",
    }
    return pd.DataFrame(rows), summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epoch-csv", type=Path, default=DEFAULT_EPOCHS)
    ap.add_argument("--pair-csv", type=Path, default=DEFAULT_PAIRS)
    ap.add_argument("--output-dir", type=Path, default=ROOT / "reviewer_outputs")
    ap.add_argument("--check", action="store_true", help="Fail if the archived 106D regression values change")
    args = ap.parse_args()

    metrics, summary = compute(args.epoch_csv, args.pair_csv, DEFAULT_FRAMES)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = args.output_dir / "Reviewer1_C3_106D_Mode_Metrics.csv"
    summary_path = args.output_dir / "Reviewer1_C3_106D_Mode_Summary.json"
    isolated_path = args.output_dir / "Reviewer1_C7_106D_Isolated_Common_Epochs.csv"
    metrics.to_csv(metrics_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    pd.DataFrame({"isolated_common_epoch": summary["isolated_common_epochs"]}).to_csv(isolated_path, index=False)

    print(metrics.to_string(index=False))
    print(json.dumps(summary, indent=2))
    print(f"Wrote: {metrics_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {isolated_path}")

    if args.check:
        expected_isolated = ["20220409", "20230323", "20230814"]
        if summary["isolated_common_epochs"] != expected_isolated:
            raise SystemExit(f"Regression check failed: isolated epochs {summary['isolated_common_epochs']} != {expected_isolated}")
        retention = summary["common_pair_retention_relative_to_smaller_common_period_network"]
        if abs(retention - 0.9398854961832062) > 1e-12:
            raise SystemExit(f"Regression check failed: retention={retention}")
        if summary["common_pair_graph_component_count"] != 4:
            raise SystemExit("Regression check failed: expected 4 common-pair graph components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
