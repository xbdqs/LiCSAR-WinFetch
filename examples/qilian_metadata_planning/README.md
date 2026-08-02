# Qilian Mountains metadata-planning example

This example contains 22 valid LiCSAR frame identifiers: 11 ascending and 11
descending frames. It is intended for remote inventory scanning and temporal
planning only.

Files:

- `qilianshan_frames.json` and `qilianshan_frames.txt`: equivalent frame lists.
- `example_group_summary.csv`: corrected relative-orbit planning statistics from
  the manuscript evidence.
- `example_planning_summary.json`: compact case-level summary.

The example does not contain GeoTIFF products and must not be used as evidence of a
22-frame raster download. `055A` and `150D` are single-frame relative-orbit groups,
so common-epoch and common-pair intersection metrics are not applicable. The 106D
exact-common-pair graph is disconnected when all common epochs, including three
isolated epochs, are retained.
