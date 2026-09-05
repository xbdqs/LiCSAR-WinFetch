#!/usr/bin/env python3
"""Compare LiCSAR-WinFetch and maintained LiCSBAS Step 01 bounded outputs.

The comparison is intentionally about correctness, not speed. It compares the
same 20 expected LiCSAR objects by relative path, size, and SHA-256 digest.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "reviewer_validation" / "manifests" / "bounded_benchmark_20_files.csv"


def sha256(path: Path, block: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("winfetch_frame_dir", type=Path)
    ap.add_argument("licsbas_frame_dir", type=Path)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--output-dir", type=Path, default=Path("reviewer_outputs"))
    args = ap.parse_args()

    expected = list(csv.DictReader(args.manifest.open(encoding="utf-8-sig", newline="")))
    rows = []
    for item in expected:
        rel = Path(item["relative_path"])
        a = args.winfetch_frame_dir / rel
        b = args.licsbas_frame_dir / rel
        a_exists = a.is_file(); b_exists = b.is_file()
        a_size = a.stat().st_size if a_exists else None
        b_size = b.stat().st_size if b_exists else None
        a_hash = sha256(a) if a_exists else None
        b_hash = sha256(b) if b_exists else None
        rows.append({
            "relative_path": rel.as_posix(),
            "winfetch_exists": a_exists,
            "licsbas_exists": b_exists,
            "winfetch_bytes": a_size,
            "licsbas_bytes": b_size,
            "size_identical": a_exists and b_exists and a_size == b_size,
            "winfetch_sha256": a_hash or "",
            "licsbas_sha256": b_hash or "",
            "sha256_identical": a_exists and b_exists and a_hash == b_hash,
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "Reviewer1_C5_WinFetch_vs_LiCSBAS01_Equivalence.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)
    summary = {
        "expected_file_count": len(rows),
        "present_in_both": sum(r["winfetch_exists"] and r["licsbas_exists"] for r in rows),
        "identical_size_count": sum(bool(r["size_identical"]) for r in rows),
        "identical_sha256_count": sum(bool(r["sha256_identical"]) for r in rows),
        "all_20_identical": all(bool(r["sha256_identical"]) for r in rows),
        "comparison_scope": "bounded correctness/equivalence only; no transfer-speed claim",
    }
    (args.output_dir / "Reviewer1_C5_WinFetch_vs_LiCSBAS01_Summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote: {csv_path}")
    return 0 if summary["all_20_identical"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
