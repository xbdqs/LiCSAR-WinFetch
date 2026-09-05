# Figure reproduction

Run from any working directory:

```bash
python plot_all_figures.py
```

The scripts resolve all paths relative to their own location and write both 600-dpi PNG and vector PDF files to `../Final`.

- Figure 1 and Figure 2 are architecture diagrams generated entirely by code.
- Figure 3 reads the preserved Qilian frame and epoch inventories.
- Figure 4 reads the validation evidence table generated from the final test records.

Required packages: `matplotlib` and `pandas`.
