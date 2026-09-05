#!/usr/bin/env python3
"""Hash every file in the bounded 20-file reviewer benchmark manifest.

The manifest may leave ``expected_size_bytes`` blank for products whose exact
source object is intentionally not fixed (currently the representative MLI).
Such files are still required to exist and are always hashed, but they are not
counted in the fixed-size validation denominator.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "reviewer_validation"
    / "manifests"
    / "bounded_benchmark_20_files.csv"
)


def sha256(path: Path, block: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest of *path*."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(block)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parse_optional_int(value: str | None) -> int | None:
    """Parse an optional integer CSV field; blank means unconstrained."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return int(text)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Compute SHA-256 for every file in the bounded 20-file benchmark "
            "manifest. Blank expected_size_bytes values are treated as "
            "size-unconstrained but still required and hashed."
        )
    )
    ap.add_argument(
        "frame_dir",
        type=Path,
        help="Frame directory containing GEOC/",
    )
    ap.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reviewer_outputs"),
    )
    args = ap.parse_args()

    with args.manifest.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise SystemExit(f"Manifest is empty: {args.manifest}")

    out: list[dict[str, object]] = []
    missing: list[str] = []

    for row in rows:
        rel = Path(row["relative_path"])
        path = args.frame_dir / rel
        expected_size = parse_optional_int(row.get("expected_size_bytes"))
        expected_out: int | str = expected_size if expected_size is not None else ""

        if not path.is_file():
            missing.append(rel.as_posix())
            out.append(
                {
                    "relative_path": rel.as_posix(),
                    "exists": False,
                    "bytes": "",
                    "expected_size_bytes": expected_out,
                    "size_matches": False if expected_size is not None else "",
                    "sha256": "",
                }
            )
            continue

        size = path.stat().st_size
        out.append(
            {
                "relative_path": rel.as_posix(),
                "exists": True,
                "bytes": size,
                "expected_size_bytes": expected_out,
                "size_matches": (
                    size == expected_size if expected_size is not None else ""
                ),
                "sha256": sha256(path),
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "Reviewer1_C6_Benchmark_SHA256_All20.csv"

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        writer.writeheader()
        writer.writerows(out)

    size_checked_count = sum(r["expected_size_bytes"] != "" for r in out)
    size_match_count = sum(r["size_matches"] is True for r in out)
    size_unconstrained_count = sum(r["expected_size_bytes"] == "" for r in out)

    summary = {
        "manifest_file_count": len(rows),
        "present_file_count": sum(bool(r["exists"]) for r in out),
        "missing_file_count": len(missing),
        "size_checked_count": size_checked_count,
        "size_match_count": size_match_count,
        "size_mismatch_count": size_checked_count - size_match_count,
        "size_unconstrained_count": size_unconstrained_count,
        "sha256_count": sum(bool(r["sha256"]) for r in out),
        "missing": missing,
    }

    summary_path = args.output_dir / "Reviewer1_C6_Benchmark_SHA256_Summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {summary_path}")

    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
