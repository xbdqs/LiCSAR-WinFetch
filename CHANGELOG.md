# Changelog

## 1.3.0 — reviewer-revision release, 2026-09-05

- Preserves `v1.2.4` unchanged as the initial-submission release.
- Confirms the Python core as cross-platform: 6/6 CI jobs passed on Windows, Ubuntu Linux and macOS under Python 3.10 and 3.12.
- Adds the 106D zero-download four-mode comparison requested during review, including explicit isolated-epoch diagnostics.
- Adds bounded correctness comparison against maintained COMET LiCSBAS Step 01 at commit `a145e6c4217b29eb7348ea95630454a099809098`.
- For frame `124D_04854_171313` over 2016-09-09 to 2016-10-03, both downloaders produced all 20 expected paths; 19/20 files were byte-identical by SHA-256, including all 12 interferogram products. The sole difference was the representative MLI source epoch.
- Computes SHA-256 for all 20 benchmark files on both sides; 19/19 fixed-size products matched expected sizes and the representative MLI is intentionally size-unconstrained.
- Revises manuscript figures/tables and reviewer evidence while retaining the original validation record as historical evidence.
- Documents tolerance-based cross-orbit date matching as a possible future extension; it is not implemented in this release.


## 1.3.0-rc1 — reviewer-revision candidate, 2026-09-04

- Preserves `v1.2.4` as the immutable initial-submission release.
- Reframes the core implementation as platform-neutral Python while retaining Windows-first project history and convenience launchers.
- Adds GitHub Actions matrix testing for Windows, Ubuntu Linux and macOS with Python 3.10 and 3.12.
- Adds a zero-download 106D four-mode temporal-network comparison for Reviewer 1 Comment 3.
- Adds exact bounded 20-file SHA-256 coverage tooling for Reviewer 1 Comment 6.
- Adds bounded LiCSAR-WinFetch versus maintained LiCSBAS Step 01 file-equivalence tooling for Reviewer 1 Comment 5.
- Adds an exact 20-file benchmark manifest and step-by-step Chinese revision-testing guide.
- Corrects public citation/notice authorship to match the submitted software manuscript author, Qingsong Du.

No `v1.3.0` release should be created until the reviewer-requested validation is completed and checked.

## 1.2.4 — 2026-08-02

Initial public submission release with resumable acquisition, structural validation, multi-frame inventory planning, Qilian metadata-only evidence, bounded transfer evidence and bounded LiCSBAS Step-02 validation.
