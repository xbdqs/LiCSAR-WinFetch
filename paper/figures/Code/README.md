# Figure reproduction

Run from any working directory:

```bash
python plot_all_figures.py
```

The scripts resolve all paths relative to their own location and write 600-dpi PNG and vector PDF files to `../Final`.

- Figure 1: acquisition, planning and validation architecture.
- Figure 2: file-reliability state path plus the actual bounded benchmark output structure.
- Figure 3: ascending/descending Qilian temporal coverage with the three isolated 106D common epochs.
- Figure 4: quantitative validation ladder and explicit evidential boundary.

Required packages: `matplotlib` and `pandas`.
