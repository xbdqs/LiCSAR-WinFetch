# Figure reproduction

Install the dependencies listed in the repository root and run:

```powershell
python paper\figures\Code\plot_all_figures.py
```

Each figure also has an independent script. Outputs are written to `Final/` as PNG
and PDF. Figure 3 reads the Qilian frame and epoch inventories; Figure 4 reads the
validation-evidence table. Figures 1 and 2 are architecture/logic diagrams encoded
directly in their scripts.
