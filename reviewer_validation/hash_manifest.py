#!/usr/bin/env python3
"""Hash an exact reviewer benchmark manifest (all 20 expected files)."""
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
        while True:
            chunk = f.read(block)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Compute SHA-256 for every file in the bounded 20-file benchmark manifest")
    ap.add_argument("frame_dir", type=Path, help="Frame directory containing GEOC/")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--output-dir", type=Path, default=Path("reviewer_outputs"))
    args = ap.parse_args()

    rows = list(csv.DictReader(args.manifest.open(encoding="utf-8-sig", newline="")))
    out = []
    missing = []
    for row in rows:
        rel = Path(row["relative_path"])
        path = args.frame_dir / rel
        expected_size = int(row["expected_size_bytes"])
        if not path.is_file():
            missing.append(rel.as_posix())
            out.append({"relative_path": rel.as_posix(), "exists": False, "bytes": "", "expected_size_bytes": expected_size, "size_matches": False, "sha256": ""})
            continue
        size = path.stat().st_size
        out.append({"relative_path": rel.as_posix(), "exists": True, "bytes": size, "expected_size_bytes": expected_size, "size_matches": size == expected_size, "sha256": sha256(path)})

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "Reviewer1_C6_Benchmark_SHA256_All20.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        writer.writeheader(); writer.writerows(out)
    summary = {
        "manifest_file_count": len(rows),
        "present_file_count": sum(bool(r["exists"]) for r in out),
        "missing_file_count": len(missing),
        "size_match_count": sum(bool(r["size_matches"]) for r in out),
        "sha256_count": sum(bool(r["sha256"]) for r in out),
        "missing": missing,
    }
    (args.output_dir / "Reviewer1_C6_Benchmark_SHA256_Summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote: {csv_path}")
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
