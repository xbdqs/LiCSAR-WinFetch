#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Automated evidence collection for the LiCSAR-WinFetch SoftwareX manuscript.

The script intentionally separates three evidence types:
1) large-area metadata-only planning (22 Qilian frames),
2) validation of an existing real downloaded frame, and
3) a bounded official tutorial-frame download used for interoperability checks.

No 22-frame GeoTIFF bulk download is performed.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import logging
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import tifffile

PAIR_RE = re.compile(r"^\d{8}_\d{8}$")
FRAME_RE = re.compile(r"^\d{3}[AD]_\d{5}_\d{6}$")

def find_project_root(start: Path) -> Path:
    """Find the enclosing validation workspace without assuming package layout."""
    for candidate in (start, *start.parents):
        if (candidate / "local_config.json").is_file() and (candidate / "outputs").is_dir():
            return candidate
    return start.parents[1]


ROOT = find_project_root(Path(__file__).resolve().parent)
OUTPUTS = ROOT / "outputs"
SOFTWARE = ROOT / "software"
QILIAN_OUT = OUTPUTS / "01_qilian_multiframe"
EXISTING_OUT = OUTPUTS / "02_existing_frame"
BENCHMARK_OUT = OUTPUTS / "03_official_benchmark"
WSL_OUT = OUTPUTS / "04_wsl_licsbas_check"
TABLES_FIGURES_OUT = OUTPUTS / "05_tables_figures"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_path(value: str | Path, base: Path = ROOT) -> Path:
    raw = str(value)
    # Accept Windows-style relative paths even when the validation code is tested
    # on another operating system. Absolute Windows paths remain untouched on Windows.
    if os.name != "nt" and "\\" in raw and not re.match(r"^[A-Za-z]:", raw):
        raw = raw.replace("\\", os.sep)
    p = Path(raw)
    if not p.is_absolute():
        p = base / p
    return p.resolve()


def load_config(path: Path) -> dict[str, Any]:
    cfg = read_json(path)
    cfg["_config_path"] = str(path.resolve())
    return cfg


def sha256_file(path: Path, chunk: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def human_bytes(n: int | float) -> str:
    n = float(n)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if abs(n) < 1024.0 or unit == units[-1]:
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} TB"


def markdown_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    view = df if max_rows is None else df.head(max_rows)
    try:
        return view.to_markdown(index=False)
    except Exception:
        return view.to_csv(index=False)


def inspect_tiff(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "valid": False,
        "shape": None,
        "dtype": None,
        "geotiff_tags_present": False,
        "error": "",
    }
    try:
        with tifffile.TiffFile(path) as tf:
            page = tf.pages[0]
            result["shape"] = list(page.shape)
            result["dtype"] = str(page.dtype)
            tag_names = set(page.tags.keys())
            # Common numeric TIFF tag codes used by GeoTIFF.
            geo_codes = {33550, 33922, 34264, 34735, 34736, 34737}
            result["geotiff_tags_present"] = bool(tag_names.intersection(geo_codes))
            result["valid"] = True
    except Exception as exc:
        result["error"] = str(exc)
    return result


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def safe_extract_zip(archive: zipfile.ZipFile, destination: Path) -> None:
    """Extract a local evidence archive without accepting path traversal."""
    root = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"Unsafe ZIP member path: {member.filename}")
    archive.extractall(destination)


def analyze_qilian(cfg: dict[str, Any]) -> dict[str, Any]:
    out = QILIAN_OUT
    out.mkdir(parents=True, exist_ok=True)
    feedback_zip = resolve_path(cfg["qilian_feedback_zip"])
    if not feedback_zip.is_file():
        result = {"status": "missing", "message": f"Feedback ZIP not found: {feedback_zip}"}
        write_json(out / "qilian_results.json", result)
        return result

    extract_dir = out / "source_feedback"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(feedback_zip) as zf:
        safe_extract_zip(zf, extract_dir)

    plan = extract_dir / "Qilian_Multiframe_Plan"
    frames = pd.read_csv(plan / "frame_summary.csv")
    groups = pd.read_csv(plan / "group_summary.csv")
    status = read_json(extract_dir / "step1_run_status.json")

    frame_ok = frames[frames["status"] == "ok"].copy()
    project_row = groups[groups["group_type"] == "project"].iloc[0]
    direction_rows = groups[groups["group_type"] == "direction"].copy()
    orbit_rows = groups[groups["group_type"] == "relative-orbit"].copy()

    orbit_retention_rows: list[dict[str, Any]] = []
    for _, row in orbit_rows.iterrows():
        group = row["group"]
        sub = frames[frames["track_group"] == group]
        min_pairs = int(sub["pair_count"].min()) if len(sub) else 0
        common_pairs = int(row["common_pair_count"])
        retention = common_pairs / min_pairs if min_pairs else None
        orbit_retention_rows.append({
            "relative_orbit": group,
            "frame_count": int(row["frame_count"]),
            "recommended_mode": row["recommended_mode"],
            "common_start": str(int(row["common_start"])),
            "common_end": str(int(row["common_end"])),
            "common_epoch_count": int(row["common_epoch_count"]),
            "common_pair_count": common_pairs,
            "minimum_frame_pair_count": min_pairs,
            "common_pair_retention_vs_smaller_frame": retention,
            "common_network_connected": bool(row["common_pair_network_connected"]),
        })
    retention_df = pd.DataFrame(orbit_retention_rows)

    result = {
        "status": "ok",
        "feedback_bundle_version": status.get("bundle_version"),
        "scan_duration_seconds": status.get("duration_seconds"),
        "frame_count": int(len(frames)),
        "successful_frames": int(len(frame_ok)),
        "ascending_frames": int((frames["direction"] == "Ascending").sum()),
        "descending_frames": int((frames["direction"] == "Descending").sum()),
        "total_epoch_records_across_frames": int(frame_ok["epoch_count"].sum()),
        "total_pair_records_across_frames": int(frame_ok["pair_count"].sum()),
        "project_common_start": str(int(project_row["common_start"])),
        "project_common_end": str(int(project_row["common_end"])),
        "project_recommended_mode": project_row["recommended_mode"],
        "relative_orbit_groups": int(len(orbit_rows)),
        "single_frame_orbit_groups": orbit_rows.loc[orbit_rows["frame_count"] == 1, "group"].tolist(),
        "frames_with_disconnected_original_network": frame_ok.loc[~frame_ok["network_connected"], "frame"].tolist(),
        "direction_periods": {
            row["group"]: {
                "common_start": str(int(row["common_start"])),
                "common_end": str(int(row["common_end"])),
                "frame_count": int(row["frame_count"]),
            }
            for _, row in direction_rows.iterrows()
        },
    }
    write_json(out / "qilian_results.json", result)
    frames.to_csv(out / "Table_Qilian_Frame_Summary.csv", index=False)
    groups.to_csv(out / "Table_Qilian_Group_Summary.csv", index=False)
    retention_df.to_csv(out / "Table_Qilian_Common_Pair_Retention.csv", index=False)
    copy_if_exists(plan / "temporal_coverage.png", out / "Figure_Qilian_Temporal_Coverage.png")
    copy_if_exists(extract_dir / "step1_planner_console.log", out / "qilian_scan_console.log")

    # One simple publication-support plot: common pairs by relative orbit.
    plot_df = retention_df.sort_values("relative_orbit")
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    ax.bar(plot_df["relative_orbit"], plot_df["common_pair_count"])
    ax.set_xlabel("Relative orbit group")
    ax.set_ylabel("Exact common interferogram pairs")
    ax.set_title("Common interferogram pairs within Qilian relative-orbit groups")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(out / "Figure_Qilian_Common_Pairs.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    narrative = f"""# Qilian multi-frame evidence (automatically generated)

- Frames scanned successfully: **{result['successful_frames']}/{result['frame_count']}**.
- Ascending/descending frames: **{result['ascending_frames']}/{result['descending_frames']}**.
- Scan duration: **{result['scan_duration_seconds']:.1f} s**.
- Project-level common analysis period: **{result['project_common_start']}–{result['project_common_end']}**.
- Relative-orbit groups: **{result['relative_orbit_groups']}**.
- Original frame networks reported as disconnected: **{', '.join(result['frames_with_disconnected_original_network']) or 'none'}**.
- The recommended project strategy is **common-period**, not a forced cross-orbit intersection of acquisition dates or interferograms.

## Direction-level common periods

{markdown_table(direction_rows[["group", "frame_count", "common_start", "common_end", "recommended_mode"]])}

## Relative-orbit planning results

{markdown_table(retention_df)}
"""
    (out / "Qilian_Results_For_Manuscript.md").write_text(narrative, encoding="utf-8")
    return result


def iter_pair_dirs(frame_dir: Path) -> list[Path]:
    geoc = frame_dir / "GEOC"
    if not geoc.is_dir():
        return []
    return sorted(p for p in geoc.iterdir() if p.is_dir() and PAIR_RE.fullmatch(p.name))


def analyze_frame_directory(frame_dir: Path, out: Path, cfg: dict[str, Any], label: str) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    if not frame_dir.is_dir():
        result = {"status": "missing", "frame_dir": str(frame_dir), "message": "Directory does not exist"}
        write_json(out / f"{label}_results.json", result)
        return result
    frame = frame_dir.name
    geoc = frame_dir / "GEOC"
    if not FRAME_RE.fullmatch(frame) or not geoc.is_dir():
        result = {"status": "invalid", "frame_dir": str(frame_dir), "message": "Not a valid frame folder containing GEOC"}
        write_json(out / f"{label}_results.json", result)
        return result

    pairs = iter_pair_dirs(frame_dir)
    pair_rows: list[dict[str, Any]] = []
    complete = 0
    missing_items: list[str] = []
    total_pair_bytes = 0
    for p in pairs:
        unw = p / f"{p.name}.geo.unw.tif"
        cc = p / f"{p.name}.geo.cc.tif"
        unw_ok = unw.is_file() and unw.stat().st_size > 0
        cc_ok = cc.is_file() and cc.stat().st_size > 0
        if unw_ok and cc_ok:
            complete += 1
        if not unw_ok:
            missing_items.append(str(unw))
        if not cc_ok:
            missing_items.append(str(cc))
        unw_size = unw.stat().st_size if unw_ok else 0
        cc_size = cc.stat().st_size if cc_ok else 0
        total_pair_bytes += unw_size + cc_size
        pair_rows.append({
            "pair": p.name,
            "unw_exists": unw_ok,
            "cc_exists": cc_ok,
            "complete": unw_ok and cc_ok,
            "unw_bytes": unw_size,
            "cc_bytes": cc_size,
        })

    aux_names = [
        f"{frame}.geo.E.tif", f"{frame}.geo.N.tif", f"{frame}.geo.U.tif",
        f"{frame}.geo.hgt.tif", f"{frame}.geo.mli.tif",
        "baselines", "network.png", "metadata.txt",
    ]
    aux_rows = []
    for name in aux_names:
        p = geoc / name
        aux_rows.append({"name": name, "exists": p.is_file() and p.stat().st_size > 0, "bytes": p.stat().st_size if p.is_file() else 0})
    gacos_count = len(list((frame_dir / "GACOS").glob("*.sltd.geo.tif"))) if (frame_dir / "GACOS").is_dir() else 0

    report_counts: dict[str, int] = {}
    report_path = frame_dir / "download_report.csv"
    if report_path.is_file():
        try:
            report_df = pd.read_csv(report_path)
            if "status" in report_df.columns:
                report_counts = {str(k): int(v) for k, v in report_df["status"].value_counts().to_dict().items()}
            report_df.to_csv(out / f"{label}_Download_Report.csv", index=False)
        except Exception as exc:
            report_counts = {"report_parse_error": 1}
            (out / f"{label}_report_parse_error.txt").write_text(str(exc), encoding="utf-8")

    # Hash auxiliary files and a deterministic sample of pairs by default.
    validation_cfg = cfg.get("file_validation", {})
    do_hash = bool(validation_cfg.get("compute_sha256", True))
    hash_all = bool(validation_cfg.get("hash_all_files", False))
    sample_pairs = int(validation_cfg.get("hash_sample_pairs", 3))
    hash_paths: list[Path] = []
    hash_large_aux = bool(validation_cfg.get("hash_large_auxiliary_files", False))
    for row in aux_rows:
        p = geoc / row["name"]
        if p.is_file() and p.stat().st_size > 0:
            # Hash small metadata products by default. Large geometry/MLI rasters
            # are inspected via TIFF headers and can be hashed only when requested.
            if hash_large_aux or p.stat().st_size <= 50 * 1024 * 1024:
                hash_paths.append(p)
    pair_selection = pairs if hash_all else pairs[:sample_pairs]
    for p in pair_selection:
        for suffix in ("unw", "cc"):
            f = p / f"{p.name}.geo.{suffix}.tif"
            if f.is_file() and f.stat().st_size > 0:
                hash_paths.append(f)
    hash_rows = []
    if do_hash:
        for p in hash_paths:
            hash_rows.append({"relative_path": str(p.relative_to(frame_dir)), "bytes": p.stat().st_size, "sha256": sha256_file(p)})

    # Inspect TIFF headers without reading full rasters.
    tiff_rows: list[dict[str, Any]] = []
    if validation_cfg.get("inspect_geotiff", True):
        inspect_paths: list[Path] = []
        for suffix in ("E", "N", "U", "hgt", "mli"):
            p = geoc / f"{frame}.geo.{suffix}.tif"
            if p.is_file():
                inspect_paths.append(p)
        if pairs:
            p = pairs[0]
            inspect_paths += [p / f"{p.name}.geo.unw.tif", p / f"{p.name}.geo.cc.tif"]
        for p in inspect_paths:
            if p.is_file() and p.stat().st_size > 0:
                rec = inspect_tiff(p)
                rec["relative_path"] = str(p.relative_to(frame_dir))
                tiff_rows.append(rec)

    result = {
        "status": "ok" if pairs and complete == len(pairs) else "incomplete",
        "frame": frame,
        "frame_dir": str(frame_dir),
        "pair_directories": len(pairs),
        "complete_pairs": complete,
        "incomplete_pairs": len(pairs) - complete,
        "pair_data_bytes": total_pair_bytes,
        "pair_data_size": human_bytes(total_pair_bytes),
        "gacos_files": gacos_count,
        "auxiliary_files_present": int(sum(bool(r["exists"]) for r in aux_rows)),
        "auxiliary_files_expected": len(aux_rows),
        "missing_required_files": missing_items,
        "download_report_status_counts": report_counts,
        "hashed_files": len(hash_rows),
        "inspected_tiffs": len(tiff_rows),
        "valid_inspected_tiffs": int(sum(bool(r["valid"]) for r in tiff_rows)),
        "licsbas_pair_structure_passed": bool(pairs and complete == len(pairs)),
    }
    write_json(out / f"{label}_results.json", result)
    pd.DataFrame(pair_rows).to_csv(out / f"Table_{label}_Pair_Completeness.csv", index=False)
    pd.DataFrame(aux_rows).to_csv(out / f"Table_{label}_Auxiliary_Files.csv", index=False)
    pd.DataFrame(hash_rows).to_csv(out / f"Table_{label}_SHA256.csv", index=False)
    pd.DataFrame(tiff_rows).to_csv(out / f"Table_{label}_TIFF_Inspection.csv", index=False)
    copy_if_exists(frame_dir / "download_summary.txt", out / f"{label}_download_summary.txt")
    copy_if_exists(frame_dir / "download.log", out / f"{label}_download.log")

    status_df = pd.DataFrame([
        {"category": "Complete pairs", "count": complete},
        {"category": "Incomplete pairs", "count": len(pairs) - complete},
        {"category": "GACOS files", "count": gacos_count},
        {"category": "Auxiliary files", "count": result["auxiliary_files_present"]},
    ])
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.bar(status_df["category"], status_df["count"])
    ax.set_ylabel("Count")
    ax.set_title(f"Validation summary for {frame}")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(out / f"Figure_{label}_Validation_Summary.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    narrative = f"""# {frame} download evidence (automatically generated)

- Interferogram pair directories: **{len(pairs)}**.
- Complete `unw`/`cc` pairs: **{complete}**.
- Incomplete pairs: **{len(pairs) - complete}**.
- Pair-product volume currently present: **{human_bytes(total_pair_bytes)}**.
- Auxiliary products present: **{result['auxiliary_files_present']}/{result['auxiliary_files_expected']}**.
- GACOS products present: **{gacos_count}**.
- LiCSBAS pair-directory structure: **{'PASSED' if result['licsbas_pair_structure_passed'] else 'FAILED'}**.
- TIFF headers inspected successfully: **{result['valid_inspected_tiffs']}/{result['inspected_tiffs']}**.
- Files hashed for reproducibility evidence: **{result['hashed_files']}**.
"""
    (out / f"{label}_Results_For_Manuscript.md").write_text(narrative, encoding="utf-8")
    return result


def analyze_existing_frame(cfg: dict[str, Any]) -> dict[str, Any]:
    out = EXISTING_OUT
    raw = str(cfg.get("existing_frame_dir", "")).strip()
    if not raw:
        out.mkdir(parents=True, exist_ok=True)
        result = {
            "status": "not_run",
            "message": "existing_frame_dir is empty in local_config.json",
        }
        write_json(out / "Existing_Real_Frame_results.json", result)
        return result
    frame_dir = resolve_path(raw)
    if not frame_dir.is_dir() or not (frame_dir / "GEOC").is_dir():
        out.mkdir(parents=True, exist_ok=True)
        result = {
            "status": "not_run",
            "message": "Configured existing_frame_dir is unavailable or does not contain GEOC",
        }
        write_json(out / "Existing_Real_Frame_results.json", result)
        return result
    return analyze_frame_directory(frame_dir, out, cfg, "Existing_Real_Frame")


def load_downloader_module():
    script = SOFTWARE / "download_licsar_windows.py"
    spec = importlib.util.spec_from_file_location("licsar_downloader", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import downloader: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def graph_connected(pairs: Iterable[str]) -> tuple[bool, int, int]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for pair in pairs:
        a, b = pair.split("_")
        adjacency[a].add(b)
        adjacency[b].add(a)
    if not adjacency:
        return False, 0, 0
    remaining = set(adjacency)
    components = 0
    largest = 0
    while remaining:
        components += 1
        seed = next(iter(remaining))
        stack = [seed]
        seen = {seed}
        remaining.remove(seed)
        while stack:
            node = stack.pop()
            for nxt in adjacency[node]:
                if nxt not in seen:
                    seen.add(nxt)
                    remaining.discard(nxt)
                    stack.append(nxt)
        largest = max(largest, len(seen))
    return components == 1, components, largest


def run_benchmark(cfg: dict[str, Any]) -> dict[str, Any]:
    out = BENCHMARK_OUT
    out.mkdir(parents=True, exist_ok=True)
    bcfg = cfg.get("benchmark", {})
    if not bcfg.get("enabled", True):
        result = {"status": "disabled"}
        write_json(out / "benchmark_results.json", result)
        return result

    configured_epoch_limit = int(bcfg.get("epoch_limit", 5))
    if configured_epoch_limit < 3 or configured_epoch_limit > 10:
        result = {
            "status": "invalid_config",
            "message": "benchmark.epoch_limit must be between 3 and 10",
        }
        write_json(out / "benchmark_results.json", result)
        return result

    d = load_downloader_module()
    frame = bcfg.get("frame", "124D_04854_171313")
    output_parent = resolve_path(bcfg.get("output_parent", "local_data/Official_Benchmark"))
    settings = d.Settings(
        frame=frame,
        start=d.parse_yyyymmdd(bcfg.get("start", "20160909")),
        end=d.parse_yyyymmdd(bcfg.get("end", "20180508")),
        output_parent=output_parent,
        workers=int(bcfg.get("workers", 4)),
        get_gacos=bool(bcfg.get("get_gacos", False)),
        download_mli=True,
        download_all_mli=False,
        retries=4,
        overwrite=False,
        dry_run=False,
        progress_interval=10.0,
    )
    logger = d.setup_logging(settings.frame_dir)
    logger.info("Paper benchmark subset runner")
    logger.info("Official tutorial frame: %s", frame)
    client = d.LiCSARClient(settings, logger)
    try:
        all_items = d.discover_items(client, settings, logger)
    except Exception as exc:
        result = {"status": "discovery_failed", "message": str(exc), "frame": frame}
        write_json(out / "benchmark_results.json", result)
        return result

    pair_names = sorted({item.local_path.parent.name for item in all_items if item.category in {"unw", "cc"} and PAIR_RE.fullmatch(item.local_path.parent.name)})
    epoch_limit = configured_epoch_limit
    all_epochs = sorted({e for pair in pair_names for e in pair.split("_")})
    selected_epochs = all_epochs[:epoch_limit]
    selected_pairs = sorted(pair for pair in pair_names if all(e in selected_epochs for e in pair.split("_")))
    # Expand cautiously if the earliest epoch subset produces too few pairs.
    expansion_limit = min(len(all_epochs), min(10, epoch_limit + 5))
    while len(selected_pairs) < 3 and len(selected_epochs) < expansion_limit:
        selected_epochs.append(all_epochs[len(selected_epochs)])
        selected_pairs = sorted(pair for pair in pair_names if all(e in selected_epochs for e in pair.split("_")))

    selected_items = []
    for item in all_items:
        if item.category in {"unw", "cc"}:
            if item.local_path.parent.name in selected_pairs:
                selected_items.append(item)
        elif item.category == "gacos":
            # Optional GACOS is limited to the selected epochs.
            if any(epoch in item.label for epoch in selected_epochs):
                selected_items.append(item)
        else:
            selected_items.append(item)

    unique: dict[str, Any] = {}
    for item in selected_items:
        unique[str(item.local_path).lower()] = item

    inventory_rows: list[dict[str, Any]] = []
    estimated_selected_bytes = 0
    for item in unique.values():
        try:
            remote_size, _, resolved_url = client.remote_info(item.url)
            inventory_status = "available"
            message = ""
        except Exception as exc:
            remote_size = None
            resolved_url = ""
            inventory_status = "unavailable"
            message = str(exc)
        if remote_size is not None:
            estimated_selected_bytes += int(remote_size)
        inventory_rows.append({
            "category": item.category,
            "label": item.label,
            "relative_path": str(item.local_path.relative_to(settings.frame_dir)),
            "inventory_status": inventory_status,
            "remote_size_bytes": remote_size if remote_size is not None else "",
            "expected_url": item.url,
            "resolved_url": resolved_url,
            "message": message,
        })
    pd.DataFrame(inventory_rows).to_csv(
        out / "Benchmark_Selected_File_Inventory.csv", index=False
    )
    logger.info("Selected benchmark epochs: %s", ", ".join(selected_epochs))
    logger.info("Selected benchmark interferograms: %d", len(selected_pairs))
    results = d.run_parallel(client, unique.values(), settings.workers, logger)
    d.write_report(settings.frame_dir / "download_report.csv", results)
    critical, warnings = d.verify_structure(settings, results)
    headline = d.print_summary(settings, results, critical, warnings, logger)

    result_counts = Counter(r.status for r in results)
    bytes_transferred = sum(int(getattr(r, "bytes_transferred", 0)) for r in results)
    selected_present_bytes = sum(
        int(r.bytes_local) for r in results
        if r.status in {"downloaded", "skipped"}
    )
    (settings.frame_dir / "download_summary.txt").write_text(
        "\n".join([
            headline,
            f"Frame: {frame}",
            f"Selected epochs: {len(selected_epochs)}",
            f"Selected pairs: {len(selected_pairs)}",
            f"Downloaded: {result_counts.get('downloaded', 0)}",
            f"Already complete: {result_counts.get('skipped', 0)}",
            f"Missing: {result_counts.get('unavailable', 0)}",
            f"Failed: {result_counts.get('failed', 0)}",
        ]) + "\n",
        encoding="utf-8",
    )
    connected, components, largest = graph_connected(selected_pairs)
    benchmark_result = {
        "status": "ok" if not critical and not any(r.status == "failed" for r in results) else "incomplete",
        "headline": headline,
        "frame": frame,
        "date_range": f"{settings.start:%Y%m%d}-{settings.end:%Y%m%d}",
        "selected_epochs": selected_epochs,
        "selected_epoch_count": len(selected_epochs),
        "selected_pairs": selected_pairs,
        "selected_pair_count": len(selected_pairs),
        "selected_network_connected": connected,
        "selected_network_components": components,
        "selected_network_largest_component_epochs": largest,
        "result_counts": dict(result_counts),
        "estimated_selected_remote_bytes": estimated_selected_bytes,
        "bytes_transferred_this_run": bytes_transferred,
        "selected_present_bytes": selected_present_bytes,
        "downloaded_files_this_run": int(result_counts.get("downloaded", 0)),
        "critical_issues": critical,
        "warnings": warnings,
        "frame_dir": str(settings.frame_dir),
    }
    write_json(out / "benchmark_selection.json", {
        "all_epoch_count_in_requested_range": len(all_epochs),
        "all_pair_count_in_requested_range": len(pair_names),
        "all_epochs_in_requested_range": all_epochs,
        "all_pairs_in_requested_range": pair_names,
        "configured_epoch_limit": epoch_limit,
        "effective_epoch_limit_after_bounded_connectivity_expansion": expansion_limit,
        "selected_epochs": selected_epochs,
        "selected_pairs": selected_pairs,
        "selected_file_count": len(unique),
        "estimated_selected_remote_bytes": estimated_selected_bytes,
    })
    write_json(out / "benchmark_results.json", benchmark_result)
    copy_if_exists(settings.frame_dir / "download_report.csv", out / "Benchmark_Download_Report.csv")
    copy_if_exists(settings.frame_dir / "download.log", out / "benchmark_download.log")

    # Reuse the common directory validator and hashing logic.
    detail = analyze_frame_directory(settings.frame_dir, out / "frame_validation", cfg, "Official_Benchmark_Frame")
    benchmark_result["frame_validation"] = detail
    write_json(out / "benchmark_results.json", benchmark_result)

    narrative = f"""# Official tutorial-frame benchmark (automatically generated)

- Frame: **{frame}**.
- The bounded benchmark selected **{len(selected_epochs)} epochs** and **{len(selected_pairs)} interferograms** from the official tutorial frame.
- Selected network connected: **{'yes' if connected else 'no'}**.
- Downloaded: **{result_counts.get('downloaded', 0)}**; already complete: **{result_counts.get('skipped', 0)}**; unavailable: **{result_counts.get('unavailable', 0)}**; failed: **{result_counts.get('failed', 0)}**.
- Bytes transferred during this run: **{bytes_transferred}**; selected files present after the run: **{selected_present_bytes} bytes**.
- Windows-side LiCSBAS pair-structure check: **{'PASSED' if detail.get('licsbas_pair_structure_passed') else 'FAILED'}**.
- The benchmark is intentionally bounded and is not a full re-download of the historical tutorial dataset.
"""
    (out / "Benchmark_Results_For_Manuscript.md").write_text(narrative, encoding="utf-8")
    return benchmark_result


def run_wsl_check(cfg: dict[str, Any]) -> dict[str, Any]:
    out = WSL_OUT
    out.mkdir(parents=True, exist_ok=True)
    wcfg = cfg.get("wsl_licsbas", {})
    if not wcfg.get("enabled", False):
        result = {"status": "disabled", "message": "Set wsl_licsbas.enabled=true in local_config.json to run this check."}
        write_json(out / "wsl_results.json", result)
        print(result["message"])
        return result

    benchmark_results_path = BENCHMARK_OUT / "benchmark_results.json"
    if not benchmark_results_path.is_file():
        result = {"status": "missing_benchmark", "message": "Run Windows validation first."}
        write_json(out / "wsl_results.json", result)
        return result
    bres = read_json(benchmark_results_path)
    frame_dir = Path(bres.get("frame_dir", ""))
    if not frame_dir.is_dir():
        result = {"status": "missing_frame_dir", "frame_dir": str(frame_dir)}
        write_json(out / "wsl_results.json", result)
        return result

    distro = str(wcfg.get("distribution", "Ubuntu"))
    bashrc = str(wcfg.get("licsbas_bashrc", "~/LiCSBAS/bashrc_LiCSBAS.sh"))
    conda_executable = str(wcfg.get("conda_executable", "")).strip()
    conda_env = str(wcfg.get("conda_env", "")).strip()
    multilook = int(wcfg.get("multilook", 1))

    geoc = frame_dir / "GEOC"
    selected_pairs = list(bres.get("selected_pairs", []))
    incomplete_pairs: list[str] = []
    for pair in selected_pairs:
        pair_dir = geoc / pair
        for suffix in ("unw", "cc"):
            tif = pair_dir / f"{pair}.geo.{suffix}.tif"
            if not tif.is_file() or tif.stat().st_size == 0:
                incomplete_pairs.append(f"{pair}:{suffix}")
    if not geoc.is_dir() or len(selected_pairs) != 6 or incomplete_pairs:
        result = {
            "status": "benchmark_precheck_failed",
            "geoc_exists": geoc.is_dir(),
            "selected_pair_count": len(selected_pairs),
            "incomplete_required_products": incomplete_pairs,
        }
        write_json(out / "licsbas_step02_results.json", result)
        write_json(out / "wsl_results.json", result)
        return result

    try:
        # wslpath accepts forward-slash Windows paths reliably; raw backslashes
        # may be consumed by argument parsing before reaching the utility.
        frame_dir_for_wslpath = str(frame_dir).replace("\\", "/")
        conv = subprocess.run(
            ["wsl", "-d", distro, "--", "wslpath", "-a", frame_dir_for_wslpath],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
    except FileNotFoundError:
        result = {"status": "wsl_unavailable", "message": "wsl.exe not found"}
        write_json(out / "wsl_results.json", result)
        return result
    if conv.returncode != 0:
        result = {"status": "path_conversion_failed", "stderr": conv.stderr}
        write_json(out / "wsl_results.json", result)
        return result
    wsl_frame = conv.stdout.strip()
    inner_cmd = (
        "set -o pipefail; "
        f"source {shlex.quote(bashrc)}; "
        f"cd {shlex.quote(wsl_frame)}; "
        f"LiCSBAS02_ml_prep.py -i GEOC -n {multilook}"
    )
    if conda_executable and conda_env:
        shell_cmd = (
            f"{shlex.quote(conda_executable)} run -n {shlex.quote(conda_env)} "
            f"bash -lc {shlex.quote(inner_cmd)}"
        )
    else:
        shell_cmd = inner_cmd

    command_text = f"wsl.exe -d {distro} -- bash -lc {shlex.quote(shell_cmd)}"
    (out / "licsbas_step02_command.txt").write_text(command_text + "\n", encoding="utf-8")
    started_utc = utc_now()
    proc = subprocess.run(
        ["wsl", "-d", distro, "--", "bash", "-lc", shell_cmd],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    finished_utc = utc_now()
    stdout_path = out / "licsbas_step02_stdout.log"
    stderr_path = out / "licsbas_step02_stderr.log"
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    generated = sorted(p.name for p in frame_dir.iterdir() if p.is_dir() and p.name.startswith("GEOCml"))
    generated_file_count = sum(
        1 for name in generated for path in (frame_dir / name).rglob("*") if path.is_file()
    )

    licsbas_path = bashrc.rsplit("/", 1)[0] if "/" in bashrc else ""
    preflight_inner = (
        f"source {shlex.quote(bashrc)}; "
        "printf 'python_version='; python --version 2>&1; "
        "printf 'licsbas_command='; command -v LiCSBAS02_ml_prep.py; "
        f"printf 'licsbas_path=%s\\n' {shlex.quote(licsbas_path)}; "
        f"printf 'licsbas_commit='; git -C {shlex.quote(licsbas_path)} rev-parse HEAD 2>/dev/null || true"
    )
    if conda_executable and conda_env:
        preflight_cmd = (
            f"{shlex.quote(conda_executable)} run -n {shlex.quote(conda_env)} "
            f"bash -lc {shlex.quote(preflight_inner)}"
        )
    else:
        preflight_cmd = preflight_inner
    preflight = subprocess.run(
        ["wsl", "-d", distro, "--", "bash", "-lc", preflight_cmd],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    environment: dict[str, str] = {}
    for line in preflight.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            environment[key.strip()] = value.strip()

    passed = proc.returncode == 0 and bool(generated) and generated_file_count > 0
    result = {
        "status": "passed" if passed else "failed",
        "return_code": proc.returncode,
        "distribution": distro,
        "python_version": environment.get("python_version", ""),
        "licsbas_command": environment.get("licsbas_command", ""),
        "licsbas_path": environment.get("licsbas_path", licsbas_path),
        "licsbas_commit": environment.get("licsbas_commit", ""),
        "bashrc": bashrc,
        "conda_executable": conda_executable,
        "conda_env": conda_env,
        "frame_dir_windows": str(frame_dir),
        "frame_dir_wsl": wsl_frame,
        "command": command_text,
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "generated_directories": generated,
        "generated_file_count": generated_file_count,
        "manual_renaming_or_reorganisation_required": False if passed else None,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
    }
    write_json(out / "licsbas_step02_results.json", result)
    write_json(out / "wsl_results.json", result)
    manuscript_note = f"""# LiCSBAS step-02 interoperability result

- Status: `{result['status']}`
- WSL distribution: `{distro}`
- Python: `{result['python_version'] or 'not reported'}`
- LiCSBAS command: `{result['licsbas_command'] or 'not reported'}`
- LiCSBAS Git commit: `{result['licsbas_commit'] or 'not available'}`
- Input: the copied four-epoch, six-pair bounded benchmark `GEOC` directory
- Exit code: `{proc.returncode}`
- Generated directories: `{', '.join(generated) if generated else 'none'}`
- Generated file count: `{generated_file_count}`
- Manual renaming or reorganisation required: `{'no' if passed else 'not established'}`

This result concerns structural recognition and LiCSBAS step-02 preparation for the bounded benchmark only. It does not validate time-series inversion or scientific pixel quality.
"""
    (out / "LiCSBAS_Step02_Results_For_Manuscript.md").write_text(manuscript_note, encoding="utf-8")
    return result


def build_validation_table() -> pd.DataFrame:
    q = read_json(QILIAN_OUT / "qilian_results.json") if (QILIAN_OUT / "qilian_results.json").is_file() else {}
    e = read_json(EXISTING_OUT / "Existing_Real_Frame_results.json") if (EXISTING_OUT / "Existing_Real_Frame_results.json").is_file() else {}
    b = read_json(BENCHMARK_OUT / "benchmark_results.json") if (BENCHMARK_OUT / "benchmark_results.json").is_file() else {}
    w = read_json(WSL_OUT / "wsl_results.json") if (WSL_OUT / "wsl_results.json").is_file() else {}
    rows = [
        {
            "Validation case": "Qilian multi-frame planning",
            "Purpose": "Large-area product discovery and temporal harmonisation without bulk GeoTIFF download",
            "Scale": f"{q.get('frame_count', 'NA')} frames",
            "Key result": f"{q.get('successful_frames', 'NA')}/{q.get('frame_count', 'NA')} scans successful; common period {q.get('project_common_start', 'NA')}-{q.get('project_common_end', 'NA')}",
            "Status": q.get("status", "not run"),
        },
        {
            "Validation case": "Existing real-frame download",
            "Purpose": "Long-running operational download, resumption, and LiCSBAS directory organisation",
            "Scale": f"{e.get('complete_pairs', 'NA')} complete pairs",
            "Key result": f"Pair structure {'passed' if e.get('licsbas_pair_structure_passed') else 'not confirmed'}; {e.get('gacos_files', 'NA')} GACOS files",
            "Status": e.get("status", "not run"),
        },
        {
            "Validation case": "Official tutorial-frame subset",
            "Purpose": "Bounded reproducible download and downstream interoperability test",
            "Scale": f"{b.get('selected_epoch_count', 'NA')} epochs / {b.get('selected_pair_count', 'NA')} pairs",
            "Key result": f"Network {'connected' if b.get('selected_network_connected') else 'not confirmed'}; benchmark status {b.get('status', 'not run')}",
            "Status": b.get("status", "not run"),
        },
        {
            "Validation case": "LiCSBAS step-02 check",
            "Purpose": "Downstream recognition without manual renaming or restructuring",
            "Scale": ", ".join(w.get("generated_directories", [])) or "NA",
            "Key result": w.get("status", "not run"),
            "Status": w.get("status", "not run"),
        },
    ]
    return pd.DataFrame(rows)


def generate_paper_materials(cfg: dict[str, Any]) -> dict[str, Any]:
    out = TABLES_FIGURES_OUT
    out.mkdir(parents=True, exist_ok=True)
    table = build_validation_table()
    table.to_csv(out / "Table_Validation_Cases.csv", index=False)

    q = read_json(QILIAN_OUT / "qilian_results.json") if (QILIAN_OUT / "qilian_results.json").is_file() else {}
    e = read_json(EXISTING_OUT / "Existing_Real_Frame_results.json") if (EXISTING_OUT / "Existing_Real_Frame_results.json").is_file() else {}
    b = read_json(BENCHMARK_OUT / "benchmark_results.json") if (BENCHMARK_OUT / "benchmark_results.json").is_file() else {}
    selection = read_json(BENCHMARK_OUT / "benchmark_selection.json") if (BENCHMARK_OUT / "benchmark_selection.json").is_file() else {}
    w = read_json(WSL_OUT / "wsl_results.json") if (WSL_OUT / "wsl_results.json").is_file() else {}

    feature_source = ROOT / "paper_materials" / "Feature_Comparison_Draft.csv"
    if feature_source.is_file():
        pd.read_csv(feature_source).to_csv(out / "Table_Feature_Comparison.csv", index=False)

    evidence_rows = [
        ["Qilian frames scanned", "outputs/01_qilian_multiframe/qilian_results.json", "frame_count; successful_frames", f"{q.get('successful_frames', 'not run')}/{q.get('frame_count', 'not run')}", "Abstract; 2.4; 3.1"],
        ["Ascending/descending counts", "outputs/01_qilian_multiframe/qilian_results.json", "ascending_frames; descending_frames", f"{q.get('ascending_frames', 'not run')}/{q.get('descending_frames', 'not run')}", "3.1"],
        ["Qilian scan duration", "outputs/01_qilian_multiframe/qilian_results.json", "scan_duration_seconds", q.get("scan_duration_seconds", "not run"), "2.4; 3.1"],
        ["Project common period", "outputs/01_qilian_multiframe/qilian_results.json", "project_common_start; project_common_end", f"{q.get('project_common_start', 'not run')}--{q.get('project_common_end', 'not run')}", "2.4; 3.1"],
        ["Relative-orbit groups", "outputs/01_qilian_multiframe/qilian_results.json", "relative_orbit_groups", q.get("relative_orbit_groups", "not run"), "3.1"],
        ["Existing-frame validation", "outputs/02_existing_frame/Existing_Real_Frame_results.json", "status", e.get("status", "not run"), "3.2"],
        ["Benchmark remote inventory", "outputs/03_official_benchmark/benchmark_selection.json", "all_epoch_count_in_requested_range; all_pair_count_in_requested_range", f"{selection.get('all_epoch_count_in_requested_range', 'not run')} epochs / {selection.get('all_pair_count_in_requested_range', 'not run')} pairs", "3.3"],
        ["Benchmark selected epochs/pairs", "outputs/03_official_benchmark/benchmark_results.json", "selected_epoch_count; selected_pair_count", f"{b.get('selected_epoch_count', 'not run')}/{b.get('selected_pair_count', 'not run')}", "Abstract; 3.3"],
        ["Benchmark transfer bytes", "outputs/03_official_benchmark/benchmark_results.json", "bytes_transferred_this_run", b.get("bytes_transferred_this_run", "not run"), "3.3"],
        ["Benchmark structure", "outputs/03_official_benchmark/benchmark_results.json", "frame_validation.licsbas_pair_structure_passed", b.get("frame_validation", {}).get("licsbas_pair_structure_passed", "not run"), "3.3"],
        ["LiCSBAS step 02", "outputs/04_wsl_licsbas_check/wsl_results.json", "status", w.get("status", "not run"), "2.5; 3.3"],
    ]
    evidence_df = pd.DataFrame(evidence_rows, columns=[
        "manuscript_claim", "evidence_file", "field_or_key", "verified_value", "manuscript_section"
    ])
    evidence_df.to_csv(out / "Table_Evidence_to_Claim.csv", index=False)

    # Architecture/workflow figure: a compact, evidence-neutral software diagram.
    fig, ax = plt.subplots(figsize=(13, 4.2))
    ax.set_axis_off()
    labels = [
        "Frame/date\nconfiguration",
        "Inventory and\nresource resolution",
        "Metadata planning\nor bounded transfer",
        "LiCSBAS-compatible\nGEOC/GACOS layout",
        "Readiness checks\nand evidence reports",
    ]
    xs = [0.02, 0.22, 0.43, 0.64, 0.84]
    colors = ["#d9eaf7", "#c7e9c0", "#fee8c8", "#e5d8bd", "#dadaeb"]
    for index, (x, label, color) in enumerate(zip(xs, labels, colors)):
        ax.text(
            x + 0.07, 0.56, label, ha="center", va="center", fontsize=10,
            transform=ax.transAxes,
            bbox={"boxstyle": "round,pad=0.55", "facecolor": color, "edgecolor": "#444444"},
        )
        if index < len(xs) - 1:
            ax.annotate(
                "", xy=(xs[index + 1], 0.56), xytext=(x + 0.145, 0.56),
                xycoords=ax.transAxes, textcoords=ax.transAxes,
                arrowprops={"arrowstyle": "->", "lw": 1.6, "color": "#444444"},
            )
    ax.text(
        0.5, 0.16,
        "Multi-frame mode stops after lightweight inventories; single-frame mode writes .part files and finalises only validated objects.",
        ha="center", va="center", fontsize=9.5, transform=ax.transAxes,
    )
    ax.set_title("LiCSAR-WinFetch architecture and bounded validation workflow", fontsize=13)
    fig.tight_layout()
    fig.savefig(out / "Figure_Software_Architecture.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # Status figure keeps not-run stages visually distinct from failures.
    status_values = [
        ("Qilian metadata\nplanning", q.get("status", "not run")),
        ("Existing real\nframe", e.get("status", "not run")),
        ("Official bounded\nbenchmark", b.get("status", "not run")),
        ("LiCSBAS\nstep 02", w.get("status", "not run")),
    ]
    def normalise_status(value: str) -> str:
        return "not run" if value in {"not_run", "disabled", "not run"} else value
    statuses = [normalise_status(str(value)) for _, value in status_values]
    palette = {"ok": "#31a354", "passed": "#31a354", "not run": "#9e9ac8", "incomplete": "#fdae6b", "failed": "#de2d26"}
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    bars = ax.bar([label for label, _ in status_values], [1] * len(status_values), color=[palette.get(value, "#969696") for value in statuses])
    ax.set_ylim(0, 1.25)
    ax.set_yticks([])
    ax.set_ylabel("")
    ax.set_title("Validation cases and execution status")
    for bar, value in zip(bars, statuses):
        ax.text(bar.get_x() + bar.get_width() / 2, 0.5, value.upper(), ha="center", va="center", color="white", fontweight="bold")
    fig.tight_layout()
    fig.savefig(out / "Figure_Validation_Status.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    replacements = {
        "{{AUTHOR_NAME}}": cfg.get("author_name", "[AUTHOR]"),
        "{{AFFILIATION}}": cfg.get("affiliation") or "[AFFILIATION]",
        "{{QILIAN_FRAME_COUNT}}": str(q.get("frame_count", "[PENDING]")),
        "{{QILIAN_SUCCESS_COUNT}}": str(q.get("successful_frames", "[PENDING]")),
        "{{QILIAN_SCAN_SECONDS}}": str(q.get("scan_duration_seconds", "[PENDING]")),
        "{{QILIAN_COMMON_START}}": str(q.get("project_common_start", "[PENDING]")),
        "{{QILIAN_COMMON_END}}": str(q.get("project_common_end", "[PENDING]")),
        "{{EXISTING_FRAME}}": str(e.get("frame", "[PENDING]")),
        "{{EXISTING_COMPLETE_PAIRS}}": str(e.get("complete_pairs", "[PENDING]")),
        "{{EXISTING_GACOS}}": str(e.get("gacos_files", "[PENDING]")),
        "{{BENCHMARK_FRAME}}": str(b.get("frame", "124D_04854_171313")),
        "{{BENCHMARK_EPOCHS}}": str(b.get("selected_epoch_count", "[PENDING]")),
        "{{BENCHMARK_PAIRS}}": str(b.get("selected_pair_count", "[PENDING]")),
        "{{BENCHMARK_STATUS}}": str(b.get("status", "[PENDING]")),
        "{{LICSBAS02_STATUS}}": str(w.get("status", "[PENDING]")),
    }
    template_path = ROOT / "paper_materials" / "SoftwareX_Manuscript_Working_Draft_EN.md"
    text = template_path.read_text(encoding="utf-8")
    for k, v in replacements.items():
        text = text.replace(k, v)
    (out / "SoftwareX_Manuscript_Autofilled_EN.md").write_text(text, encoding="utf-8")

    summary = f"""# Paper evidence status

Generated: {utc_now()}

## Validation evidence

{markdown_table(table)}

## Files ready for manuscript use

- `01_qilian_multiframe/Figure_Qilian_Temporal_Coverage.png`
- `01_qilian_multiframe/Table_Qilian_Frame_Summary.csv`
- `01_qilian_multiframe/Table_Qilian_Group_Summary.csv`
    - `02_existing_frame/Existing_Real_Frame_results.json`
- `03_official_benchmark/benchmark_results.json`
    - `05_tables_figures/Table_Validation_Cases.csv`
    - `05_tables_figures/SoftwareX_Manuscript_Autofilled_EN.md`

## Remaining manual checks

1. Confirm author affiliation and email in `local_config.json`.
2. Run the optional WSL LiCSBAS step-02 check and regenerate paper materials.
3. Review all automatically generated statements against the logs before submission.
4. Create the public repository and fixed release archive only after the software version is frozen.
"""
    (out / "PAPER_EVIDENCE_STATUS.md").write_text(summary, encoding="utf-8")
    result = {
        "status": "ok",
        "generated": utc_now(),
        "validation_rows": len(table),
        "figures_generated": 2,
        "tables_generated": 3,
    }
    write_json(out / "paper_generation_status.json", result)
    return result


def environment_snapshot() -> str:
    lines = [
        f"Generated UTC: {utc_now()}",
        f"Python: {sys.version}",
        f"Executable: {sys.executable}",
        f"Platform: {platform.platform()}",
        f"Machine: {platform.machine()}",
        f"Working directory: {Path.cwd()}",
    ]
    try:
        proc = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, check=False)
        lines += ["", "pip freeze:", proc.stdout]
    except Exception as exc:
        lines += ["", f"pip freeze failed: {exc}"]
    return "\n".join(lines)


def collect_feedback(cfg: dict[str, Any]) -> Path:
    feedback_dir = ROOT / "feedback_packages"
    feedback_dir.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = feedback_dir / f"LiCSAR_WinFetch_Paper_Feedback_{stamp}.zip"
    snapshot = OUTPUTS / "environment_snapshot.txt"
    snapshot.write_text(environment_snapshot(), encoding="utf-8")
    config_copy = dict(cfg)
    config_copy.pop("_config_path", None)
    write_json(OUTPUTS / "local_config_used.json", config_copy)

    excluded_suffixes = {".tif", ".tiff", ".part", ".pyc"}
    max_file_bytes = 25 * 1024 * 1024

    def feedback_safe(path: Path) -> bool:
        return (
            path.is_file()
            and path.suffix.lower() not in excluded_suffixes
            and "__pycache__" not in path.parts
            and path.stat().st_size <= max_file_bytes
        )

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for base in [OUTPUTS, ROOT / "codex_outputs", ROOT / "paper_materials", ROOT / "release_materials"]:
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if feedback_safe(path):
                    zf.write(path, path.relative_to(ROOT))
        # Include small benchmark reports stored beside the downloaded files, never TIFFs.
        bres_path = BENCHMARK_OUT / "benchmark_results.json"
        if bres_path.is_file():
            bres = read_json(bres_path)
            bdir = Path(bres.get("frame_dir", ""))
            if bdir.is_dir():
                for name in ["download_report.csv", "download_summary.txt", "download.log", "licsbas02_validation.log"]:
                    p = bdir / name
                    if feedback_safe(p):
                        zf.write(p, Path("benchmark_external_reports") / name)
        for p in [ROOT / "local_config.json", ROOT / "START_HERE_CN.md", ROOT / "UPLOAD_CHECKLIST_CN.md"]:
            if p.is_file():
                zf.write(p, p.name)
    print(f"Feedback package: {zip_path}")
    return zip_path


def run_windows(cfg: dict[str, Any]) -> int:
    OUTPUTS.mkdir(exist_ok=True)
    status: dict[str, Any] = {"started_utc": utc_now(), "stages": {}}
    print("[1/3] Analysing the completed 22-frame Qilian scan...")
    status["stages"]["qilian"] = analyze_qilian(cfg)
    print("[2/3] Analysing the existing real-frame download directory...")
    status["stages"]["existing"] = analyze_existing_frame(cfg)
    print("[3/3] Running the bounded official tutorial-frame benchmark...")
    status["stages"]["benchmark"] = run_benchmark(cfg)
    status["finished_utc"] = utc_now()
    write_json(OUTPUTS / "windows_validation_status.json", status)
    generate_paper_materials(cfg)
    # Missing existing path is a configuration issue, but all other evidence is retained.
    severe = status["stages"]["qilian"].get("status") != "ok" or status["stages"]["benchmark"].get("status") not in {"ok", "disabled"}
    return 1 if severe else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LiCSAR-WinFetch paper evidence runner")
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ["run-windows", "run-wsl", "generate-paper", "collect"]:
        p = sub.add_parser(cmd)
        p.add_argument("--config", type=Path, default=ROOT / "local_config.json")
    args = parser.parse_args()
    cfg = load_config(args.config.resolve())
    if args.command == "run-windows":
        return run_windows(cfg)
    if args.command == "run-wsl":
        result = run_wsl_check(cfg)
        generate_paper_materials(cfg)
        return 0 if result.get("status") in {"passed", "disabled"} else 1
    if args.command == "generate-paper":
        generate_paper_materials(cfg)
        return 0
    if args.command == "collect":
        collect_feedback(cfg)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
