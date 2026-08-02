#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify that a downloaded frame follows the LiCSBAS GEOC/GACOS layout."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FRAME_RE = re.compile(r"^\d{3}[AD]_\d{5}_\d{6}$")
PAIR_RE = re.compile(r"^\d{8}_\d{8}$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frame_dir", type=Path, help="Frame directory containing GEOC")
    parser.add_argument(
        "--strict", action="store_true",
        help="Also fail when optional geometry/MLI/metadata products are absent"
    )
    args = parser.parse_args()
    frame_dir = args.frame_dir.resolve()
    frame = frame_dir.name
    if not FRAME_RE.fullmatch(frame):
        print(f"ERROR: folder name is not a valid frame ID: {frame}")
        return 2
    geoc = frame_dir / "GEOC"
    if not geoc.is_dir():
        print(f"ERROR: missing {geoc}")
        return 2

    critical: list[str] = []
    warnings: list[str] = []
    auxiliary = [
        f"{frame}.geo.E.tif", f"{frame}.geo.N.tif",
        f"{frame}.geo.U.tif", f"{frame}.geo.hgt.tif",
        f"{frame}.geo.mli.tif", "baselines", "metadata.txt", "network.png",
    ]
    for name in auxiliary:
        path = geoc / name
        if not path.is_file() or path.stat().st_size == 0:
            warnings.append(f"missing or empty auxiliary file: GEOC/{name}")

    pairs = sorted(p for p in geoc.iterdir() if p.is_dir() and PAIR_RE.fullmatch(p.name))
    if not pairs:
        critical.append("no interferogram pair folders")
    for pair in pairs:
        for suffix in ("unw", "cc"):
            path = pair / f"{pair.name}.geo.{suffix}.tif"
            if not path.is_file() or path.stat().st_size == 0:
                critical.append(f"missing or empty: GEOC/{pair.name}/{path.name}")

    if critical or (args.strict and warnings):
        print("FAILED")
        for issue in critical:
            print(" - CRITICAL:", issue)
        for warning in warnings:
            print(" - OPTIONAL:", warning)
        return 1

    print("PASSED")
    print(f"Frame: {frame}")
    print(f"Interferogram pairs: {len(pairs)}")
    print(f"GEOC: {geoc}")
    if warnings:
        print("Optional-product warnings:")
        for warning in warnings:
            print(" -", warning)
    if (frame_dir / "GACOS").is_dir():
        print(f"GACOS files: {len(list((frame_dir / 'GACOS').glob('*.sltd.geo.tif')))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
