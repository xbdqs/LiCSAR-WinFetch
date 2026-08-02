#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Multi-frame temporal coverage and interferogram-network planner for LiCSAR.

Phase-1 design principles
-------------------------
1. Exact common epochs/pairs are scientifically meaningful primarily for frames
   on the same relative orbit (e.g. two adjacent 070A frames).
2. Across different relative orbits, the recommended harmonisation is a common
   analysis period rather than identical acquisition dates or interferograms.
3. This planner scans remote listings only; it does not download GeoTIFF data.

Outputs include frame-, track-, direction- and project-level summaries, epoch
and pair inventories, recommended common periods, network diagnostics, and a
machine-readable plan for later integration with the downloader.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import logging
import math
import os
import re
import sys
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
except Exception:  # plotting remains optional
    plt = None
    mdates = None

from tqdm import tqdm

from download_licsar_windows import (
    DATE_RE,
    DEFAULT_BASE_URL,
    FRAME_RE,
    PAIR_RE,
    LiCSARClient,
    Settings,
    base_frame_url,
    expected_url,
    parse_yyyymmdd,
)

VERSION = "1.2.4"


@dataclass
class FrameInventory:
    frame: str
    direction: str
    track_group: str
    epochs: list[str]
    pairs: list[str]
    status: str = "ok"
    message: str = ""

    @property
    def first_epoch(self) -> Optional[str]:
        return self.epochs[0] if self.epochs else None

    @property
    def last_epoch(self) -> Optional[str]:
        return self.epochs[-1] if self.epochs else None

    @property
    def baseline_days(self) -> list[int]:
        values: list[int] = []
        for pair in self.pairs:
            a = parse_yyyymmdd(pair[:8])
            b = parse_yyyymmdd(pair[9:])
            values.append((b - a).days)
        return values


@dataclass
class NetworkDiagnostics:
    epoch_count: int
    pair_count: int
    component_count: int
    largest_component_epochs: int
    connected: bool
    isolated_epoch_count: int
    largest_gap_days: Optional[int]


def validate_frame(frame: str) -> str:
    value = frame.strip()
    if not FRAME_RE.fullmatch(value):
        raise ValueError(f"Invalid LiCSAR frame ID: {value}")
    return value


def load_frames(path: Path) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    frames: list[str] = []
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, list):
            raw = data
        elif isinstance(data, dict):
            raw = []
            for key in ("frames", "ascending", "descending"):
                values = data.get(key, [])
                if isinstance(values, list):
                    raw.extend(values)
        else:
            raise ValueError("Frame JSON must be a list or an object.")
        frames = [validate_frame(str(value)) for value in raw]
    else:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            frames.append(validate_frame(value))
    seen: set[str] = set()
    unique: list[str] = []
    for frame in frames:
        if frame not in seen:
            unique.append(frame)
            seen.add(frame)
    if not unique:
        raise ValueError("No valid frames were found.")
    return unique


def frame_direction(frame: str) -> str:
    return "Ascending" if frame[3] == "A" else "Descending"


def track_group(frame: str) -> str:
    return frame[:4]


def make_settings(
    frame: str,
    start: dt.date,
    end: dt.date,
    output: Path,
    base_url: str,
    retries: int,
    timeout_connect: float,
    timeout_read: float,
    verify_tls: bool,
) -> Settings:
    return Settings(
        frame=frame,
        start=start,
        end=end,
        output_parent=output,
        workers=1,
        base_url=base_url,
        retries=retries,
        timeout_connect=timeout_connect,
        timeout_read=timeout_read,
        verify_tls=verify_tls,
        dry_run=True,
    )


def scan_frame(
    frame: str,
    start: dt.date,
    end: dt.date,
    output: Path,
    base_url: str,
    retries: int,
    timeout_connect: float,
    timeout_read: float,
    verify_tls: bool,
) -> FrameInventory:
    settings = make_settings(
        frame, start, end, output, base_url, retries,
        timeout_connect, timeout_read, verify_tls,
    )
    logger = logging.getLogger(f"planner.{frame}")
    client = LiCSARClient(settings, logger)
    epoch_error: Optional[Exception] = None
    pair_error: Optional[Exception] = None
    epochs: list[str] = []
    pairs: list[str] = []

    # Scan the two remote inventories independently. Some valid LiCSAR frames
    # expose interferograms but do not publish a separate epochs directory.
    # In that case, acquisition dates can be recovered exactly from the pair IDs.
    try:
        epochs = [
            value for value in client.list_names(expected_url(settings, "epochs", ""), DATE_RE)
            if start <= parse_yyyymmdd(value) <= end
        ]
    except Exception as exc:
        epoch_error = exc

    try:
        for value in client.list_names(
            expected_url(settings, "interferograms", ""), PAIR_RE
        ):
            first = parse_yyyymmdd(value[:8])
            second = parse_yyyymmdd(value[9:])
            if first >= start and second <= end:
                pairs.append(value)
    except Exception as exc:
        pair_error = exc

    if pairs:
        pair_epochs = {endpoint for pair in pairs for endpoint in pair_endpoints(pair)}
        if not epochs:
            epochs = sorted(pair_epochs)
        else:
            # Include endpoints present in valid interferograms even when the
            # epochs listing is incomplete or slightly stale.
            epochs = sorted(set(epochs) | pair_epochs)

    notes: list[str] = []
    if epoch_error is not None and pairs:
        notes.append(
            "Epoch directory unavailable; acquisition dates were derived from interferogram pair names. "
            f"Original epoch-listing error: {epoch_error}"
        )
    if pair_error is not None and epochs:
        notes.append(f"Interferogram directory unavailable: {pair_error}")

    if pairs:
        return FrameInventory(
            frame=frame,
            direction=frame_direction(frame),
            track_group=track_group(frame),
            epochs=sorted(set(epochs)),
            pairs=sorted(set(pairs)),
            status="ok",
            message=" ".join(notes),
        )

    errors = []
    if epoch_error is not None:
        errors.append(f"epochs: {epoch_error}")
    if pair_error is not None:
        errors.append(f"interferograms: {pair_error}")
    if not errors:
        errors.append("No interferogram pairs were found in the requested date range.")
    return FrameInventory(
        frame=frame,
        direction=frame_direction(frame),
        track_group=track_group(frame),
        epochs=sorted(set(epochs)),
        pairs=[],
        status="failed",
        message=" | ".join(errors),
    )


def pair_endpoints(pair: str) -> tuple[str, str]:
    return pair[:8], pair[9:]


def network_diagnostics(epochs: Iterable[str], pairs: Iterable[str]) -> NetworkDiagnostics:
    epoch_set = set(epochs)
    pair_list = list(dict.fromkeys(pairs))
    for pair in pair_list:
        a, b = pair_endpoints(pair)
        epoch_set.add(a)
        epoch_set.add(b)
    adjacency: dict[str, set[str]] = {epoch: set() for epoch in epoch_set}
    for pair in pair_list:
        a, b = pair_endpoints(pair)
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)

    visited: set[str] = set()
    component_sizes: list[int] = []
    for node in sorted(adjacency):
        if node in visited:
            continue
        queue = deque([node])
        visited.add(node)
        size = 0
        while queue:
            current = queue.popleft()
            size += 1
            for nxt in adjacency.get(current, ()):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        component_sizes.append(size)

    ordered_dates = sorted(parse_yyyymmdd(value) for value in epoch_set)
    largest_gap = None
    if len(ordered_dates) >= 2:
        largest_gap = max((b - a).days for a, b in zip(ordered_dates, ordered_dates[1:]))
    isolated = sum(1 for node in adjacency if not adjacency[node])
    component_count = len(component_sizes)
    return NetworkDiagnostics(
        epoch_count=len(epoch_set),
        pair_count=len(pair_list),
        component_count=component_count,
        largest_component_epochs=max(component_sizes, default=0),
        connected=(component_count == 1 and bool(epoch_set)),
        isolated_epoch_count=isolated,
        largest_gap_days=largest_gap,
    )


def common_period(inventories: Sequence[FrameInventory]) -> tuple[Optional[str], Optional[str]]:
    valid = [inv for inv in inventories if inv.epochs]
    if not valid:
        return None, None
    start = max(inv.first_epoch for inv in valid if inv.first_epoch)
    end = min(inv.last_epoch for inv in valid if inv.last_epoch)
    if start is None or end is None or start > end:
        return None, None
    return start, end


def intersection(values: Sequence[Sequence[str]]) -> list[str]:
    if not values:
        return []
    sets = [set(value) for value in values]
    if not sets:
        return []
    return sorted(set.intersection(*sets))


def selected_for_mode(
    inventory: FrameInventory,
    mode: str,
    group_inventories: Sequence[FrameInventory],
) -> tuple[list[str], list[str]]:
    if mode == "independent":
        return inventory.epochs, inventory.pairs
    if mode == "common-period":
        start, end = common_period(group_inventories)
        if not start or not end:
            return [], []
        epochs = [e for e in inventory.epochs if start <= e <= end]
        pairs = [p for p in inventory.pairs if p[:8] >= start and p[9:] <= end]
        return epochs, pairs
    if mode == "common-epochs":
        common = set(intersection([inv.epochs for inv in group_inventories]))
        epochs = sorted(common)
        pairs = [p for p in inventory.pairs if p[:8] in common and p[9:] in common]
        return epochs, pairs
    if mode == "common-pairs":
        # Preserve every exact common epoch, including epochs that become
        # isolated after exact pair intersection, so connectivity diagnostics
        # cannot silently discard them.
        epochs = intersection([inv.epochs for inv in group_inventories])
        pairs = intersection([inv.pairs for inv in group_inventories])
        return epochs, pairs
    raise ValueError(f"Unknown mode: {mode}")


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_temporal_coverage(
    inventories: Sequence[FrameInventory], output: Path
) -> Optional[Path]:
    if plt is None or mdates is None:
        return None
    valid = [inv for inv in inventories if inv.epochs]
    if not valid:
        return None
    ordered = sorted(valid, key=lambda inv: (inv.direction, inv.track_group, inv.frame))
    height = max(6.0, 0.36 * len(ordered) + 1.8)
    fig, ax = plt.subplots(figsize=(13, height))
    for y, inv in enumerate(ordered):
        dates = [parse_yyyymmdd(epoch) for epoch in inv.epochs]
        ax.scatter(dates, [y] * len(dates), s=8)
        if dates:
            ax.hlines(y, min(dates), max(dates), linewidth=0.7)
    ax.set_yticks(range(len(ordered)))
    ax.set_yticklabels([inv.frame for inv in ordered])
    ax.set_xlabel("Acquisition date")
    ax.set_ylabel("LiCSAR frame")
    ax.set_title("LiCSAR multi-frame temporal coverage")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="x", linewidth=0.4)
    fig.autofmt_xdate()
    fig.tight_layout()
    path = output / "temporal_coverage.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


def summarize_group(
    name: str,
    group_type: str,
    inventories: Sequence[FrameInventory],
    recommended_mode: str,
    exact_intersection_applicable: bool,
) -> dict:
    valid = [inv for inv in inventories if inv.status == "ok" and inv.epochs]
    start, end = common_period(valid)
    baselines = [days for inv in valid for days in inv.baseline_days]
    baseline_counts = Counter(baselines)
    top_baselines = ";".join(
        f"{days}:{count}" for days, count in baseline_counts.most_common(8)
    )

    applicable = bool(exact_intersection_applicable and len(valid) >= 2)
    row = {
        "group": name,
        "group_type": group_type,
        "frame_count": len(inventories),
        "successful_frames": len(valid),
        "failed_frames": len(inventories) - len(valid),
        "recommended_mode": recommended_mode,
        "common_start": start or "",
        "common_end": end or "",
        "exact_intersection_applicable": applicable,
        "common_epoch_count": "",
        "common_pair_count": "",
        "minimum_pair_count_in_common_period": "",
        "exact_common_pair_retention_vs_smaller_period_network": "",
        "exact_common_pair_jaccard": "",
        "common_pair_network_connected": "",
        "common_pair_components": "",
        "common_pair_isolated_epochs": "",
        "common_pair_largest_gap_days": "",
        "single_frame_original_network_connected": "",
        "dominant_temporal_baselines_days_count": top_baselines,
    }

    if len(valid) == 1:
        diag = network_diagnostics(valid[0].epochs, valid[0].pairs)
        row["single_frame_original_network_connected"] = diag.connected

    if not applicable or not start or not end:
        return row

    restricted_epochs = [
        [epoch for epoch in inv.epochs if start <= epoch <= end]
        for inv in valid
    ]
    restricted_pairs = [
        [pair for pair in inv.pairs if pair[:8] >= start and pair[9:] <= end]
        for inv in valid
    ]
    common_epochs = intersection(restricted_epochs)
    common_pairs = intersection(restricted_pairs)
    diag = network_diagnostics(common_epochs, common_pairs)
    min_period_pairs = min((len(values) for values in restricted_pairs), default=0)
    union_pairs = set().union(*(set(values) for values in restricted_pairs))

    row.update({
        "common_epoch_count": len(common_epochs),
        "common_pair_count": len(common_pairs),
        "minimum_pair_count_in_common_period": min_period_pairs,
        "exact_common_pair_retention_vs_smaller_period_network": (
            len(common_pairs) / min_period_pairs if min_period_pairs else ""
        ),
        "exact_common_pair_jaccard": (
            len(common_pairs) / len(union_pairs) if union_pairs else ""
        ),
        "common_pair_network_connected": diag.connected,
        "common_pair_components": diag.component_count,
        "common_pair_isolated_epochs": diag.isolated_epoch_count,
        "common_pair_largest_gap_days": (
            diag.largest_gap_days if diag.largest_gap_days is not None else ""
        ),
    })
    return row


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan and harmonise temporal coverage for multiple LiCSAR frames.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--frames", type=Path, required=True, help="TXT or JSON frame list")
    parser.add_argument("--output", type=Path, required=True, help="Output planning directory")
    parser.add_argument("--start", default="20141001", help="Earliest date YYYYMMDD")
    parser.add_argument("--end", default=dt.date.today().strftime("%Y%m%d"), help="Latest date YYYYMMDD")
    parser.add_argument("--workers", type=int, default=6, help="Parallel frame scans")
    parser.add_argument(
        "--mode",
        choices=("independent", "common-period", "common-epochs", "common-pairs"),
        default="common-period",
        help="Selection mode used for per-track download plans",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--timeout-connect", type=float, default=20.0)
    parser.add_argument("--timeout-read", type=float, default=180.0)
    parser.add_argument("--no-verify-tls", action="store_true")
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    start = parse_yyyymmdd(args.start)
    end = parse_yyyymmdd(args.end)
    if start > end:
        raise SystemExit("Start date must not be later than end date.")
    if args.workers < 1 or args.workers > 32:
        raise SystemExit("--workers must be between 1 and 32.")

    frames = load_frames(args.frames)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.WARNING)

    print(f"LiCSAR multi-frame planner v{VERSION}")
    print(f"Frames: {len(frames)}")
    print(f"Date range: {args.start}-{args.end}")
    print(f"Output: {output}")
    print("Scientific rule: exact common epochs/pairs are planned within the same relative orbit; cross-track groups use a common period.")

    inventories: list[FrameInventory] = []
    with ThreadPoolExecutor(max_workers=min(args.workers, len(frames))) as pool:
        futures = {
            pool.submit(
                scan_frame,
                frame,
                start,
                end,
                output,
                args.base_url.rstrip("/") + "/",
                args.retries,
                args.timeout_connect,
                args.timeout_read,
                not args.no_verify_tls,
            ): frame
            for frame in frames
        }
        with tqdm(total=len(futures), desc="Frame scan", unit="frame", dynamic_ncols=True) as bar:
            for future in as_completed(futures):
                inv = future.result()
                inventories.append(inv)
                if inv.status == "ok":
                    tqdm.write(
                        f"[OK] {inv.frame}: {len(inv.epochs)} epochs, {len(inv.pairs)} pairs"
                    )
                else:
                    tqdm.write(f"[FAIL] {inv.frame}: {inv.message}")
                bar.update(1)

    inventories.sort(key=lambda inv: (inv.direction, inv.track_group, inv.frame))

    frame_rows = []
    epoch_rows = []
    pair_rows = []
    for inv in inventories:
        diag = network_diagnostics(inv.epochs, inv.pairs)
        baseline_counts = Counter(inv.baseline_days)
        frame_rows.append({
            "frame": inv.frame,
            "direction": inv.direction,
            "track_group": inv.track_group,
            "status": inv.status,
            "message": inv.message,
            "first_epoch": inv.first_epoch or "",
            "last_epoch": inv.last_epoch or "",
            "epoch_count": len(inv.epochs),
            "pair_count": len(inv.pairs),
            "network_connected": diag.connected,
            "network_components": diag.component_count,
            "largest_component_epochs": diag.largest_component_epochs,
            "largest_gap_days": diag.largest_gap_days if diag.largest_gap_days is not None else "",
            "dominant_baselines": ";".join(
                f"{days}:{count}" for days, count in baseline_counts.most_common(8)
            ),
        })
        epoch_rows.extend({"frame": inv.frame, "epoch": epoch} for epoch in inv.epochs)
        for pair in inv.pairs:
            a, b = pair_endpoints(pair)
            pair_rows.append({
                "frame": inv.frame,
                "pair": pair,
                "primary_epoch": a,
                "secondary_epoch": b,
                "temporal_baseline_days": (parse_yyyymmdd(b) - parse_yyyymmdd(a)).days,
            })

    write_csv(
        output / "frame_summary.csv",
        [
            "frame", "direction", "track_group", "status", "message",
            "first_epoch", "last_epoch", "epoch_count", "pair_count",
            "network_connected", "network_components", "largest_component_epochs",
            "largest_gap_days", "dominant_baselines",
        ],
        frame_rows,
    )
    write_csv(output / "epoch_inventory.csv", ["frame", "epoch"], epoch_rows)
    write_csv(
        output / "pair_inventory.csv",
        ["frame", "pair", "primary_epoch", "secondary_epoch", "temporal_baseline_days"],
        pair_rows,
    )

    by_track: dict[str, list[FrameInventory]] = defaultdict(list)
    by_direction: dict[str, list[FrameInventory]] = defaultdict(list)
    for inv in inventories:
        by_track[inv.track_group].append(inv)
        by_direction[inv.direction].append(inv)

    group_rows: list[dict] = []
    for group, members in sorted(by_track.items()):
        recommended = args.mode if len(members) > 1 else "independent"
        group_rows.append(summarize_group(group, "relative-orbit", members, recommended, len(members) > 1))
    for direction, members in sorted(by_direction.items()):
        group_rows.append(summarize_group(direction, "direction", members, "common-period", False))
    group_rows.append(summarize_group("All frames", "project", inventories, "common-period", False))
    write_csv(
        output / "group_summary.csv",
        [
            "group", "group_type", "frame_count", "successful_frames", "failed_frames",
            "recommended_mode", "common_start", "common_end",
            "exact_intersection_applicable", "common_epoch_count", "common_pair_count",
            "minimum_pair_count_in_common_period",
            "exact_common_pair_retention_vs_smaller_period_network",
            "exact_common_pair_jaccard", "common_pair_network_connected",
            "common_pair_components", "common_pair_isolated_epochs",
            "common_pair_largest_gap_days", "single_frame_original_network_connected",
            "dominant_temporal_baselines_days_count",
        ],
        group_rows,
    )

    plans: dict = {
        "planner_version": VERSION,
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "requested_range": {"start": args.start, "end": args.end},
        "scientific_policy": {
            "within_relative_orbit": args.mode,
            "across_relative_orbits": "common-period",
            "note": "Exact common epochs/pairs are not recommended across different relative orbits because acquisition calendars differ.",
        },
        "track_groups": {},
        "direction_groups": {},
    }

    plan_root = output / "plans"
    plan_root.mkdir(exist_ok=True)
    for group, members in sorted(by_track.items()):
        valid_members = [inv for inv in members if inv.status == "ok" and inv.pairs]
        mode = args.mode if len(valid_members) > 1 else "independent"
        group_start, group_end = common_period(valid_members)
        group_plan = {
            "group": group,
            "mode": mode,
            "common_period": {"start": group_start, "end": group_end},
            "frames": {},
        }
        for inv in members:
            group_dir = plan_root / group
            group_dir.mkdir(exist_ok=True)
            if inv.status != "ok" or not inv.pairs:
                epochs, pairs = [], []
                diag = network_diagnostics([], [])
                warning = f"Frame scan failed and was excluded from the download plan: {inv.message}"
            else:
                epochs, pairs = selected_for_mode(inv, mode, valid_members)
                diag = network_diagnostics(epochs, pairs)
                warnings: list[str] = []
                if not diag.connected:
                    warnings.append(
                        f"Selected network has {diag.component_count} components; "
                        "review isolated epochs before LiCSBAS inversion."
                    )
                if mode == "common-pairs" and not diag.connected:
                    warnings.append(
                        "Exact-common-pair mode is not recommended for this group."
                    )
                warning = " ".join(warnings)
            frame_plan = {
                "frame": inv.frame,
                "status": inv.status,
                "scan_note": inv.message,
                "mode": mode,
                "selected_epoch_count": len(epochs),
                "selected_pair_count": len(pairs),
                "network": asdict(diag),
                "epochs_file": f"plans/{group}/{inv.frame}_epochs.txt",
                "pairs_file": f"plans/{group}/{inv.frame}_pairs.txt",
                "warning": warning,
            }
            (group_dir / f"{inv.frame}_epochs.txt").write_text(
                "\n".join(epochs) + ("\n" if epochs else ""), encoding="utf-8"
            )
            (group_dir / f"{inv.frame}_pairs.txt").write_text(
                "\n".join(pairs) + ("\n" if pairs else ""), encoding="utf-8"
            )
            group_plan["frames"][inv.frame] = frame_plan
        plans["track_groups"][group] = group_plan

    for direction, members in sorted(by_direction.items()):
        ds, de = common_period(members)
        plans["direction_groups"][direction] = {
            "mode": "common-period",
            "common_period": {"start": ds, "end": de},
            "frame_count": len(members),
        }

    (output / "download_plan.json").write_text(
        json.dumps(plans, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    plot_path = plot_temporal_coverage(inventories, output)

    failed = [inv for inv in inventories if inv.status != "ok"]
    print("\nPlanning completed")
    print(f"Successful frame scans: {len(inventories) - len(failed)}/{len(inventories)}")
    print(f"Track groups: {len(by_track)}")
    print(f"Reports: {output}")
    if plot_path:
        print(f"Temporal coverage figure: {plot_path}")
    if failed:
        print("Some frames failed to scan. Review frame_summary.csv and rerun; successful inventories remain in the reports.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
